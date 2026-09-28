"""Pełny kształt wypożyczeń (okno „Szczegóły” w omnis-mobile) i osobna historia — SPEC.md REQ-L1..REQ-L5.

Surowe `httpx` dla kluczy, których `omnis-py` nie deklaruje (pydantic je ignoruje), plus prawdziwy
`OmnisClient` tam, gdzie liczy się to, że nowy kształt nadal się parsuje (aktywne i `type=history`).
"""

import re
from collections.abc import AsyncIterator
from datetime import date

import httpx
import pytest
from omnis.client import OmnisClient

from omnis_mock import auth as mock_auth
from omnis_mock import data as mock_data
from omnis_mock.main import app

INSTITUTION = "MOCK"
VIEW = "MOCK:MOCK"
LOANS_URL = "/primaws/rest/priv/myaccount/loans"
RENEW_URL = "/primaws/rest/priv/myaccount/renew_loans"

REQ10_KEYS = {
    "loanid",
    "mmsid",
    "title",
    "duedate",
    "duehour",
    "loandate",
    "loanstatus",
    "ilsinstitutionname",
    "mainlocationname",
    "itembarcode",
    "renew",
}
COMMON_L1_KEYS = {
    "callnumber2",
    "year",
    "itemcategorycode",
    "itemcategoryname",
    "itemstatusname",
    "itemid",
    "mainlocationcode",
    "secondarylocationcode",
    "ilsinstitutioncode",
    "nzmmsid",
    "nzilsinstitutioncode",
}
ACTIVE_ONLY_KEYS = {"maxrenewdate", "renewstatuses", "alerts"}
HISTORY_ONLY_KEYS = {"returndate", "returnhour"}


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


@pytest.fixture
async def headers(http: httpx.AsyncClient) -> dict[str, str]:
    response = await http.post(
        "/primaws/suprimaLogin",
        data={"username": mock_data.DEMO_USERNAME, "password": mock_data.DEMO_PASSWORD},
    )
    return {"Authorization": f"Bearer {response.json()['jwtData']}"}


async def _loans_envelope(http: httpx.AsyncClient, headers: dict[str, str], loan_type: str) -> dict:
    response = await http.get(
        LOANS_URL, headers=headers, params={"bulk": "50", "lang": "pl", "offset": "1", "type": loan_type}
    )
    assert response.status_code == 200
    return response.json()["data"]["loans"]


async def _active(http: httpx.AsyncClient, headers: dict[str, str]) -> dict[str, dict]:
    return {loan["loanid"]: loan for loan in (await _loans_envelope(http, headers, "active"))["loan"]}


async def _renew(http: httpx.AsyncClient, headers: dict[str, str], loan_id: str) -> None:
    response = await http.post(RENEW_URL, headers=headers, params={"lang": "pl"}, json={"id": loan_id})
    assert response.status_code == 200


def _display_title(title: str) -> str:
    """Kopia `displayTitle` z omnis-mobile (`Models.kt`) — obcięcie przed " / "."""
    return re.split(r"\s+/\s+", title, maxsplit=1)[0].strip().rstrip(".,:;=").strip() or title


def _renew_messages(renewstatuses: dict) -> list[str]:
    """Jak `renewStatusMessages` w omnis-mobile: lista albo goły string."""
    inner = renewstatuses["renewstatus"]
    return [inner] if isinstance(inner, str) else inner


# --- REQ-L1 / REQ-L3 ---


async def test_active_loans_have_full_primo_shape(http: httpx.AsyncClient, headers: dict[str, str]) -> None:
    envelope = await _loans_envelope(http, headers, "active")
    assert envelope["historicloans"] == "Y"
    assert envelope["hasAlerts"] is False
    assert "Y" not in envelope["showmore"]

    for loan in envelope["loan"]:
        missing = (REQ10_KEYS | COMMON_L1_KEYS | ACTIVE_ONLY_KEYS) - loan.keys()
        assert not missing, f"{loan['loanid']}: brak {missing}"
        assert not (HISTORY_ONLY_KEYS & loan.keys())
        assert loan["duehour"] == "2359"
        assert re.fullmatch(r"\d{4}\.", loan["year"])
        assert re.fullmatch(r"\d{8}", loan["maxrenewdate"])
        assert loan["maxrenewdate"] >= loan["duedate"]
        assert loan["alerts"] == []
        assert loan["loanstatus"] in {"Zwykłe", "Prolongowano"}


async def test_titles_addresses_and_codes_are_realistic(http: httpx.AsyncClient, headers: dict[str, str]) -> None:
    loans = list((await _active(http, headers)).values())
    with_slash = [loan for loan in loans if " / " in loan["title"]]
    assert len(with_slash) > len(loans) / 2, "REQ-L3: większość tytułów z oznaczeniem odpowiedzialności"
    assert len(with_slash) < len(loans), "REQ-L3: jeden tytuł bez „ / ”"
    assert _display_title(with_slash[0]["title"]) != with_slash[0]["title"]

    addresses = [loan["secondarylocationname"] for loan in loans]
    assert None in addresses
    assert any(address and address.startswith("ul. ") for address in addresses)

    # Kody lokalizacji i adres są spójne z holdingiem tego samego rekordu w katalogu (REQ-G6).
    for loan in loans:
        record = await http.get(f"/primaws/rest/pub/pnxs/L/alma{loan['mmsid']}", params={"vid": VIEW})
        holding = record.json()["delivery"]["holding"][0]
        assert holding["libraryCode"] == loan["mainlocationcode"]
        if loan["secondarylocationname"] is not None:
            assert holding["subLocation"] == loan["secondarylocationname"]
        assert loan["year"] == f"{record.json()['pnx']['display']['creationdate'][0]}."


async def test_default_loanstatus_is_regular(http: httpx.AsyncClient, headers: dict[str, str]) -> None:
    loans = await _active(http, headers)
    assert loans["loan-001"]["loanstatus"] == "Zwykłe"


# --- REQ-L2 ---


async def test_non_renewable_loans_explain_why(http: httpx.AsyncClient, headers: dict[str, str]) -> None:
    loans = (await _active(http, headers)).values()
    non_renewable = [loan for loan in loans if loan["renew"] == "N"]
    messages = [tuple(_renew_messages(loan["renewstatuses"])) for loan in non_renewable]
    assert all(messages), "REQ-L2: każde nieodnawialne wypożyczenie ma komunikat"
    assert len(set(messages)) >= 2, "REQ-L2: różne powody"
    assert any(isinstance(loan["renewstatuses"]["renewstatus"], str) for loan in non_renewable)
    assert ("Okres, na który można dokonać prolongaty to 7 dni przed datą zwrotu",) in messages


# --- REQ-13 / REQ-L3 / REQ-L5 ---


async def test_renewal_sets_status_and_respects_maxrenewdate(http: httpx.AsyncClient, headers: dict[str, str]) -> None:
    before = (await _active(http, headers))["loan-001"]
    await _renew(http, headers, "loan-001")
    after = (await _active(http, headers))["loan-001"]
    assert after["duedate"] > before["duedate"]
    assert after["loanstatus"] == "Prolongowano"

    # Prolonguj aż do limitu — termin nigdy nie przekracza maxrenewdate, a kolejne wywołania to no-op 200.
    for _ in range(5):
        await _renew(http, headers, "loan-001")
    capped = (await _active(http, headers))["loan-001"]
    assert capped["duedate"] <= capped["maxrenewdate"]
    await _renew(http, headers, "loan-001")
    assert (await _active(http, headers))["loan-001"]["duedate"] == capped["duedate"]


async def test_non_renewable_loan_does_not_change(http: httpx.AsyncClient, headers: dict[str, str]) -> None:
    before = (await _active(http, headers))["loan-003"]
    await _renew(http, headers, "loan-003")
    after = (await _active(http, headers))["loan-003"]
    assert after["duedate"] == before["duedate"]
    assert after["loanstatus"] == before["loanstatus"]


# --- REQ-L4 ---


async def test_history_is_separate_list_of_returned_loans(http: httpx.AsyncClient, headers: dict[str, str]) -> None:
    envelope = await _loans_envelope(http, headers, "history")
    history = envelope["loan"]
    assert "Y" not in envelope["showmore"]
    assert envelope["historicloans"] == "Y"
    assert 3 <= len(history) <= 5
    assert not ({loan["loanid"] for loan in history} & (await _active(http, headers)).keys())

    today = date.today().strftime("%Y%m%d")
    for loan in history:
        missing = (REQ10_KEYS | COMMON_L1_KEYS | HISTORY_ONLY_KEYS) - loan.keys()
        assert not missing, f"{loan['loanid']}: brak {missing}"
        assert not (ACTIVE_ONLY_KEYS & loan.keys())
        assert loan["renew"] == "N"
        assert loan["loandate"] <= loan["returndate"] < today
        assert re.fullmatch(r"\d{4}", loan["returnhour"])
        # Rekord katalogu istnieje, więc omnis-mobile dociągnie autora/serię także dla historii.
        record = await http.get(f"/primaws/rest/pub/pnxs/L/alma{loan['mmsid']}", params={"vid": VIEW})
        assert "pnx" in record.json()

    assert {loan["loanstatus"] for loan in history} == {"Zwykłe", "Prolongowano"}
    assert any(loan["itemcategoryname"] == "Ubytkowany" for loan in history)


async def test_counters_count_active_loans_only(http: httpx.AsyncClient, headers: dict[str, str]) -> None:
    response = await http.get("/primaws/rest/priv/myaccount/counters", headers=headers)
    actions = {a["type"]: a["value"] for a in response.json()["data"]["listofactions"]["action"]}
    assert actions["Loans"] == str(len(await _active(http, headers)))


async def test_omnis_py_parses_active_and_history() -> None:
    transport = httpx.ASGITransport(app=app)
    http_client = httpx.AsyncClient(transport=transport, base_url="http://mock.local")
    client = OmnisClient(base_url="http://mock.local", client=http_client)
    try:
        await client.login(mock_data.DEMO_USERNAME, mock_data.DEMO_PASSWORD, institution=INSTITUTION, view=VIEW)
        active = await client.get_loans()
        history = await client.get_loans("history")
    finally:
        await client.close()
    assert {loan.id for loan in active}.isdisjoint({loan.id for loan in history})
    assert all(loan.due_date < date.today().strftime("%Y%m%d") for loan in history)
    assert all(not loan.renewable for loan in history)
