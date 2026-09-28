"""Anonimowe wyszukiwanie (token gościa) i wyszukiwanie po autorze — SPEC.md REQ-G1..REQ-G5.

Ścieżka REQ-G2 (cały pipeline wyszukiwarki z tokenem gościa) przechodzi przez prawdziwy `OmnisClient` z
`omnis-py` — tak jak `tests/test_search_contract.py`, z tą różnicą, że klient NIE loguje się, tylko dostaje
token gościa (dokładnie to, co robi omnis-mobile). Reszta to surowe `httpx`, bo `omnis-py` nie ma API do
`guestJwt`, nie wysyła `q=creator,...`, a pułapka REQ-G3 (`"data": null` przy 200) wywaliłaby
`OmnisClient.get_loans()` zamiast dać się sprawdzić.
"""

import base64
import json
from collections.abc import AsyncIterator
from datetime import date, timedelta

import httpx
import pytest
from omnis.client import OmnisClient

from omnis_mock import auth as mock_auth
from omnis_mock import data as mock_data
from omnis_mock.main import app

INSTITUTION = "MOCK"
VIEW = "MOCK:MOCK"
GUEST_JWT_URL = f"/primaws/rest/pub/institution/{INSTITUTION}/guestJwt"
GUEST_JWT_PARAMS = {"isGuest": "true", "lang": "pl", "targetUrl": "http://x", "viewId": VIEW}
GUEST_DENIED = {
    "beaconO22": "0",
    "status": "failed",
    "reply-code": "0002",
    "reply-text": "The patron ID is invalid",
    "data": None,
}


@pytest.fixture(autouse=True)
def _reset_mock_state() -> None:
    mock_data.reset_state()
    mock_auth.reset_state()
    yield
    mock_data.reset_state()
    mock_auth.reset_state()


@pytest.fixture
async def http() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://mock.local") as client:
        yield client


async def _guest_token(http: httpx.AsyncClient) -> str:
    response = await http.get(GUEST_JWT_URL, params=GUEST_JWT_PARAMS)
    assert response.status_code == 200
    return response.text.strip('"')


async def _login_token(http: httpx.AsyncClient) -> str:
    response = await http.post(
        "/primaws/suprimaLogin",
        data={"username": mock_data.DEMO_USERNAME, "password": mock_data.DEMO_PASSWORD},
    )
    return response.json()["jwtData"]


def _decode_payload(token: str) -> dict:
    payload_b64 = token.split(".")[1]
    payload_b64 += "=" * ((4 - len(payload_b64) % 4) % 4)
    return json.loads(base64.b64decode(payload_b64).decode("utf-8"))


def _search_params(q: str, scope: str | None = "MyInstitution") -> dict[str, str]:
    params = {"q": q, "vid": VIEW, "inst": INSTITUTION, "tab": "LibraryCatalog", "limit": "10", "offset": "0"}
    if scope is not None:
        params["scope"] = scope
    return params


# --- REQ-G1 ---


async def test_guest_jwt_returns_quoted_string_token(http: httpx.AsyncClient) -> None:
    """REQ-G1: body to literał stringu JSON (nie obiekt `jwtData`), Content-Type z charsetem, 3 segmenty,
    payload dekodowalny zwykłym `b64decode` (standardowy alfabet, jak REQ-4)."""
    response = await http.get(GUEST_JWT_URL, params=GUEST_JWT_PARAMS)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json;charset=UTF-8"
    token = response.json()
    assert isinstance(token, str)
    assert response.text == f'"{token}"'
    assert token.count(".") == 2

    payload = _decode_payload(token)
    assert payload["userGroup"] == "GUEST"
    assert payload["displayName"] is None
    assert payload["userName"].startswith("anonymous-")
    assert payload["user"] == payload["userName"]
    assert payload["institution"] == INSTITUTION
    assert payload["viewId"] == VIEW


async def test_guest_jwt_without_params_returns_400(http: httpx.AsyncClient) -> None:
    """REQ-G1: brak parametrów (w szczególności `viewId`) -> 400 z pustym body."""
    response = await http.get(GUEST_JWT_URL)
    assert response.status_code == 400
    assert response.content == b""


# --- REQ-G2 ---


async def test_full_search_pipeline_with_guest_token_via_real_client(http: httpx.AsyncClient) -> None:
    """REQ-G2: prawdziwy `OmnisClient` BEZ logowania, z tokenem gościa — cały pipeline `pnxs` -> `delivery`
    -> `getPhysicalService` -> `ILSServices/holdings`. Asercja na `due_date` (nie tylko na liczbie wyników)
    dowodzi, że holdings przyjął token gościa: `omnis-py` łyka błędy HTTP z tego kroku po cichu."""
    client = OmnisClient(base_url="http://mock.local", client=http)
    client.token = await _guest_token(http)
    client.view = VIEW
    client.institution = INSTITUTION

    results = await client.search_books("Nibylandii")

    assert len(results) == 1
    unavailable = next(v for v in results[0].versions if v.mmsid == "MOCK-SEARCH-A2")
    branch = unavailable.branches[0]
    assert branch.status == "unavailable"
    assert branch.due_date == (date.today() + timedelta(days=-5)).strftime("%d/%m/%Y")
    assert branch.overdue is True


async def test_ils_holdings_works_without_authorization_header(http: httpx.AsyncClient) -> None:
    """REQ-G2 (wierność): `priv/ILSServices/holdings` działa bez nagłówka `Authorization`, jak prawdziwe
    Primo. Pułapka `holKey` (REQ-18b) bez zmian — tu z `holKey`, więc termin zwrotu musi wrócić."""
    delivery = await http.post("/primaws/rest/pub/delivery", json=["almaMOCK-SEARCH-C1"])
    holding = delivery.json()[0]["delivery"]["holding"][0]

    response = await http.post(
        "/primaws/rest/priv/ILSServices/holdings/PS-MOCK-SEARCH-C1", json={"locations": [holding]}
    )

    assert response.status_code == 200
    items = response.json()["data"]["itemInfo"]["locations"][0]["items"]
    expected_due = (date.today() + timedelta(days=12)).strftime("%d/%m/%Y")
    assert items == [{"itemstatusname": f"Wypożyczenie do {expected_due}"}]


# --- REQ-G3 ---


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", "/primaws/rest/priv/myaccount/loans", None),
        ("GET", "/primaws/rest/priv/myaccount/counters", None),
        ("POST", "/primaws/rest/priv/myaccount/renew_loans", {"id": "loan-001"}),
    ],
)
async def test_guest_token_on_myaccount_returns_200_failed(
    http: httpx.AsyncClient, method: str, path: str, body: dict | None
) -> None:
    """REQ-G3 (pułapka): token gościa na `myaccount/*` -> 200 (NIE 401) z `"status": "failed"`. Klient
    sprawdzający tylko kod HTTP uzna to za sukces."""
    token = await _guest_token(http)
    response = await http.request(method, path, headers={"Authorization": f"Bearer {token}"}, json=body)

    assert response.status_code == 200
    assert response.json() == GUEST_DENIED


async def test_guest_renew_does_not_mutate_loans(http: httpx.AsyncClient) -> None:
    """REQ-G3: odrzucona prolongata tokenem gościa nie może przesunąć terminu widocznego po zalogowaniu."""
    login_headers = {"Authorization": f"Bearer {await _login_token(http)}"}
    guest_headers = {"Authorization": f"Bearer {await _guest_token(http)}"}

    def due_of_loan_001(loans_response: httpx.Response) -> str:
        return next(
            loan["duedate"] for loan in loans_response.json()["data"]["loans"]["loan"] if loan["loanid"] == "loan-001"
        )

    before = due_of_loan_001(await http.get("/primaws/rest/priv/myaccount/loans", headers=login_headers))
    await http.post("/primaws/rest/priv/myaccount/renew_loans", headers=guest_headers, json={"id": "loan-001"})
    after = due_of_loan_001(await http.get("/primaws/rest/priv/myaccount/loans", headers=login_headers))

    assert after == before


async def test_unknown_token_on_myaccount_still_401(http: httpx.AsyncClient) -> None:
    """REQ-G3: brak tokena / nieznany token — bez zmian, 401 (REQ-5/REQ-8)."""
    unknown = await http.get("/primaws/rest/priv/myaccount/loans", headers={"Authorization": "Bearer a.b.c"})
    missing = await http.get("/primaws/rest/priv/myaccount/counters")
    assert unknown.status_code == 401
    assert missing.status_code == 401


# --- REQ-G4 ---


@pytest.mark.parametrize("scope", ["MyInstitution", "MyInstitution2", None])
async def test_known_or_missing_scope_is_accepted(http: httpx.AsyncClient, scope: str | None) -> None:
    """REQ-G4: `MyInstitution` (nowe omnis-mobile), `MyInstitution2` (omnis-py, starsze omnis-mobile) i brak
    parametru działają normalnie."""
    response = await http.get("/primaws/rest/pub/pnxs", params=_search_params("any,contains,Nibylandii", scope))
    assert response.status_code == 200
    assert len(response.json()["docs"]) == 1


async def test_unknown_scope_returns_400_with_empty_body(http: httpx.AsyncClient) -> None:
    """REQ-G4 (wierność): nieznany `scope` -> 400 z pustym body, jak prawdziwe Primo."""
    response = await http.get("/primaws/rest/pub/pnxs", params=_search_params("any,contains,Nibylandii", "Bogus"))
    assert response.status_code == 400
    assert response.content == b""


# --- REQ-G5 ---


async def _titles(http: httpx.AsyncClient, q: str) -> list[str]:
    response = await http.get("/primaws/rest/pub/pnxs", params=_search_params(q))
    assert response.status_code == 200
    return [doc["pnx"]["addata"]["btitle"][0] for doc in response.json()["docs"]]


async def test_creator_search_with_comma_in_value(http: httpx.AsyncClient) -> None:
    """REQ-G5: wartość `au` z wyniku ("Nazwisko, Imię") wysłana jako `q=creator,contains,<au>` wraca do tego
    samego rekordu — dowód, że `q` dzieli się tylko na dwóch pierwszych przecinkach."""
    au = (await http.get("/primaws/rest/pub/pnxs", params=_search_params("any,contains,Nibylandii"))).json()["docs"][0][
        "pnx"
    ]["addata"]["au"][0]
    assert au == "Nibylska, Karolina"

    assert await _titles(http, f"creator,contains,{au}") == ["Cienie Nibylandii"]


async def test_creator_search_matches_author_only_not_title(http: httpx.AsyncClient) -> None:
    """REQ-G5: `creator` zawęża do autora — słowo z tytułu nic nie znajduje, choć w `any` trafia."""
    assert await _titles(http, "any,contains,Cienie") == ["Cienie Nibylandii"]
    assert await _titles(http, "creator,contains,Cienie") == []


async def test_creator_search_returns_all_works_of_author(http: httpx.AsyncClient) -> None:
    """REQ-G5: autor z dwoma dziełami w katalogu (oba z wypożyczeń demo) — oba wyniki, w obu zapisach
    autora (z przecinkiem i bez), case-insensitive."""
    expected = sorted(["Pan Tadeusz", "Dziady"])
    assert sorted(await _titles(http, "creator,contains,Mickiewicz, Adam")) == expected
    assert sorted(await _titles(http, "creator,contains,mickiewicz adam")) == expected
    assert sorted(await _titles(http, "creator,contains,Adam Mickiewicz")) == expected
