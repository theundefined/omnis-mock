"""Zamówienia (rezerwacje) — SPEC.md REQ-H1..REQ-H12, docs/PLAN.md Faza 6.

Dwie warstwy:
- surowe `httpx` (limit, TTL z wstrzykniętym zegarem, seed, pułapki "holds" vs "hold", gość, 400, `allowed: "N"`),
  działa z każdym `omnis-py`;
- pełny przepływ PRAWDZIWYM `OmnisClient` (`get_holdable_items` -> `get_hold_options` -> `place_hold` -> ...).
  Metody składania zamówień są w `omnis-py` >= 0.2.14 (minimum w `pyproject.toml`). Bramka `hasattr` zostaje
  na wypadek starszego klienta w środowisku — wtedy te testy są pomijane (`skip`), nie wywalają się.
"""

from collections.abc import AsyncIterator
from datetime import datetime, timedelta

import httpx
import pytest
from omnis.client import OmnisClient

from omnis_mock import auth as mock_auth
from omnis_mock import data as mock_data
from omnis_mock.main import app

INSTITUTION = "MOCK"
VIEW = "MOCK:MOCK"
SEED_ID = "MOCK-REQ-0001"
ITEM_A1 = "MOCK-ITEM-MOCK-SEARCH-A1-1"
ITEM_A1_READING_ROOM = "MOCK-ITEM-MOCK-SEARCH-A1-2"  # allowed "N"
ITEM_A2 = "MOCK-ITEM-MOCK-SEARCH-A2-1"
ITEM_B1 = "MOCK-ITEM-MOCK-SEARCH-B1-1"  # item seeda

requires_hold_api = pytest.mark.skipif(
    not hasattr(OmnisClient, "place_hold"), reason="zainstalowany omnis-py nie ma składania zamówień"
)


@pytest.fixture(autouse=True)
def _reset_mock_state() -> None:
    """Stan zamówień jest modułowy i publiczny (REQ-H1) — bez resetu wyciekałby między testami i plikami."""
    mock_data.reset_state()
    mock_auth.reset_state()
    yield
    mock_data.reset_state()
    mock_auth.reset_state()


@pytest.fixture
async def http() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://mock.local") as c:
        yield c


@pytest.fixture
async def client(http: httpx.AsyncClient) -> AsyncIterator[OmnisClient]:
    omnis_client = OmnisClient(base_url="http://mock.local", client=http)
    await omnis_client.login(mock_data.DEMO_USERNAME, mock_data.DEMO_PASSWORD, institution=INSTITUTION, view=VIEW)
    yield omnis_client


def _auth(client: OmnisClient) -> dict[str, str]:
    return {"Authorization": f"Bearer {client.token}"}


async def _guest_headers(http: httpx.AsyncClient) -> dict[str, str]:
    response = await http.get(
        f"/primaws/rest/pub/institution/{INSTITUTION}/guestJwt", params={"isGuest": "true", "viewId": VIEW}
    )
    return {"Authorization": f"Bearer {response.json()}"}


def _item_url(mmsid: str, item_id: str) -> str:
    return f"/primaws/rest/priv/ILSServices/itemServices/{mmsid}/item/{item_id}/PS-{mmsid}/AlmaItemRequest"


async def _place(http: httpx.AsyncClient, client: OmnisClient, mmsid: str, item_id: str, pickup: str = "MOCKLIB-FD1"):
    body = {
        "requestType": "hold",
        "pickupLocation": pickup,
        "materialType": "BOOK",
        "itemId": item_id,
        "group_id": mmsid,
        "pickupLibraryId": pickup,
        "pickupType": "LIBRARY",
    }
    return await http.post(_item_url(mmsid, item_id), params={"lang": "pl"}, headers=_auth(client), json=body)


async def _holds(http: httpx.AsyncClient, client: OmnisClient) -> list[dict]:
    response = await http.get("/primaws/rest/priv/myaccount/requests", params={"lang": "pl"}, headers=_auth(client))
    return response.json()["data"]["holds"]["hold"]


async def _requests_counter(client: OmnisClient) -> str:
    counters = await client.client.get(
        "/primaws/rest/priv/myaccount/counters", headers=_auth(client), params={"lang": "pl"}
    )
    return next(a["value"] for a in counters.json()["data"]["listofactions"]["action"] if a["type"] == "Requests")


# --- REQ-H3/H4/H5/H6: seed i kształt (działa z omnis-py >= 0.2.10) ---------------------------------------------


async def test_requests_has_six_categories_and_one_seed_hold(client: OmnisClient, http: httpx.AsyncClient) -> None:
    response = await http.get("/primaws/rest/priv/myaccount/requests", headers=_auth(client))
    data = response.json()["data"]
    assert set(data) == {"holds", "photocopies", "bookings", "cdls", "ills", "acqs"}
    assert data["photocopies"] == {"photocopy": []} and data["acqs"] == {"acq": []}
    (hold,) = data["holds"]["hold"]
    assert set(hold) == {
        "requestid",
        "title",
        "author",
        "holdstatus",
        "available",
        "cancel",
        "pickuplocationname",
        "requestdate",
        "mmsid",
        "ilsinstitutionname",
        "ilsinstitutioncode",
    }
    assert all(isinstance(v, str) for v in hold.values())  # REQ-H5: "Y"/"N", nie bool
    assert (hold["available"], hold["cancel"]) == ("Y", "Y")
    assert hold["holdstatus"].startswith("Na półce rezerwacji do ")
    assert hold["title"].startswith("Ostatni Rejs Wyobraźni /")  # tytuł z katalogu, nie z wypożyczeń
    assert hold["requestdate"] == datetime.now().strftime("%Y%m%d")


async def test_real_client_get_requests_parses_seed(client: OmnisClient) -> None:
    items = await client.get_requests()
    assert [i.category for i in items] == ["hold"]
    assert items[0].hold is not None and items[0].hold.available is True
    assert await _requests_counter(client) == "1"


async def test_requests_denied_for_guest_and_anonymous(http: httpx.AsyncClient) -> None:
    anonymous = await http.get("/primaws/rest/priv/myaccount/requests")
    assert anonymous.status_code == 401
    guest = await http.get("/primaws/rest/priv/myaccount/requests", headers=await _guest_headers(http))
    assert guest.status_code == 200  # REQ-G3: 200, nie 401
    assert guest.json()["status"] == "failed" and guest.json()["reply-code"] == "0002"


async def test_guest_cannot_cancel_and_state_is_untouched(client: OmnisClient, http: httpx.AsyncClient) -> None:
    response = await http.post(
        "/primaws/rest/priv/myaccount/cancel_requests",
        headers=await _guest_headers(http),
        json={"request_id": SEED_ID, "request_type": "holds"},
    )
    assert response.status_code == 200 and response.json()["status"] == "failed"
    assert [h["requestid"] for h in await _holds(http, client)] == [SEED_ID]


# --- REQ-H11: cancel_requests ------------------------------------------------------------------------------------


async def test_cancel_via_real_client_removes_seed_and_counter(client: OmnisClient) -> None:
    result = await client.cancel_hold(SEED_ID)
    assert result["reply-code"] == "0000" and result["status"] == "ok"
    assert result["data"]["holds"]["hold"] == [{"requestid": SEED_ID, "note": {"type": "info"}}]
    assert await client.get_requests() == []
    assert await _requests_counter(client) == "0"


async def test_cancel_with_singular_hold_is_noop(client: OmnisClient, http: httpx.AsyncClient) -> None:
    """REQ-H11 (pułapka): `"hold"` (liczba pojedyncza) to 200 bez zmiany stanu."""
    response = await http.post(
        "/primaws/rest/priv/myaccount/cancel_requests",
        headers=_auth(client),
        json={"request_id": SEED_ID, "request_type": "hold"},
    )
    assert response.status_code == 200
    assert [h["requestid"] for h in await _holds(http, client)] == [SEED_ID]


async def test_cancel_unknown_id_is_noop(client: OmnisClient, http: httpx.AsyncClient) -> None:
    response = await http.post(
        "/primaws/rest/priv/myaccount/cancel_requests",
        headers=_auth(client),
        json={"request_id": "nie-ma-takiego", "request_type": "holds"},
    )
    assert response.status_code == 200
    assert len(await _holds(http, client)) == 1


# --- REQ-H10a/H10b: formularz i składanie (surowy HTTP) -----------------------------------------------------------


async def test_item_services_require_login_token(client: OmnisClient, http: httpx.AsyncClient) -> None:
    url = _item_url("MOCK-SEARCH-A1", ITEM_A1)
    assert (await http.get(url)).status_code == 401
    assert (await http.get(url, headers=await _guest_headers(http))).status_code == 401
    assert (await http.get(f"/primaws/rest/priv/ILSServices/itemQueue/{ITEM_A1}")).status_code == 401
    assert (await http.get(url, headers=_auth(client))).status_code == 200


async def test_form_pickup_keys_have_double_dollar_format_and_two_places_exist(
    client: OmnisClient, http: httpx.AsyncClient
) -> None:
    form = (await http.get(_item_url("MOCK-SEARCH-A1", ITEM_A1), headers=_auth(client))).json()
    (service,) = form["services-arr"]["services"]
    (group,) = service["groups-list-map"]
    assert group["requestType"] == "hold" and group["materialType"]["key"] == "BOOK"
    keys = [p["key"] for p in group["pickupLocation"]]
    assert len(keys) == 2  # REQ-H10a: filia z dwoma miejscami odbioru
    assert all(len(k.split("$$")) == 2 and all(k.split("$$")) for k in keys)
    one_place = (await http.get(_item_url("MOCK-SEARCH-B1", ITEM_B1), headers=_auth(client))).json()
    assert len(one_place["services-arr"]["services"][0]["groups-list-map"][0]["pickupLocation"]) == 1


async def test_place_hold_envelope_and_state(client: OmnisClient, http: httpx.AsyncClient) -> None:
    response = await _place(http, client, "MOCK-SEARCH-A1", ITEM_A1)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"beaconO22", "reply-text", "status"}  # REQ-H10b: bez requestid
    assert (body["status"], body["reply-text"]) == ("ok", "ok") and isinstance(body["beaconO22"], str)

    holds = await _holds(http, client)
    new = next(h for h in holds if h["requestid"] != SEED_ID)
    assert (new["holdstatus"], new["available"], new["mmsid"]) == ("W realizacji", "N", "MOCK-SEARCH-A1")
    assert new["pickuplocationname"] == "Filia Demo 1"
    assert new["title"] == "Cienie Nibylandii / Karolina Nibylska."
    assert await _requests_counter(client) == "2"
    queue = await http.get(f"/primaws/rest/priv/ILSServices/itemQueue/{ITEM_A1}", headers=_auth(client))
    assert queue.json() == {"itemId": ITEM_A1, "itemQueueString": "(zamówienie: 1)"}


async def test_second_pickup_place_is_accepted_with_its_name(client: OmnisClient, http: httpx.AsyncClient) -> None:
    assert (await _place(http, client, "MOCK-SEARCH-A1", ITEM_A1, pickup="MOCKLIB-FD1C")).status_code == 200
    names = [h["pickuplocationname"] for h in await _holds(http, client)]
    assert "Filia Demo 1 (czytelnia)" in names


async def test_place_hold_validation_returns_400(client: OmnisClient, http: httpx.AsyncClient) -> None:
    assert (await _place(http, client, "MOCK-SEARCH-A1", ITEM_A1, pickup="MOCKLIB-ZLA")).status_code == 400
    assert (await _place(http, client, "MOCK-SEARCH-A1", "MOCK-ITEM-NIE-MA")).status_code == 400
    assert (await _place(http, client, "MOCK-SEARCH-A1", ITEM_A1_READING_ROOM)).status_code == 400  # allowed "N"
    assert len(await _holds(http, client)) == 1  # żadne nie zmieniło stanu


async def test_guest_cannot_place_hold(http: httpx.AsyncClient) -> None:
    response = await http.post(
        _item_url("MOCK-SEARCH-A1", ITEM_A1),
        headers=await _guest_headers(http),
        json={"requestType": "hold", "pickupLocation": "MOCKLIB-FD1", "itemId": ITEM_A1},
    )
    assert response.status_code == 401


# --- REQ-H2: limit i TTL -------------------------------------------------------------------------------------


async def test_limit_evicts_oldest_user_hold_and_keeps_seed(client: OmnisClient, http: httpx.AsyncClient) -> None:
    clock = [datetime(2026, 1, 1, 12, 0, 0)]
    mock_data.set_clock(lambda: clock[0])
    placed: list[str] = []
    for _ in range(mock_data.MAX_ACTIVE_HOLDS + 2):
        before = {h["requestid"] for h in await _holds(http, client)}
        assert (await _place(http, client, "MOCK-SEARCH-A2", ITEM_A2, pickup="MOCKLIB-FD2")).status_code == 200
        clock[0] += timedelta(minutes=1)
        placed.append(next(h["requestid"] for h in await _holds(http, client) if h["requestid"] not in before))

    ids = [h["requestid"] for h in await _holds(http, client)]
    assert len(ids) == mock_data.MAX_ACTIVE_HOLDS
    assert SEED_ID in ids  # seed nigdy nie wypada przez limit
    assert ids[1:] == placed[-(mock_data.MAX_ACTIVE_HOLDS - 1) :]  # wypadły najstarsze użytkownika
    assert await _requests_counter(client) == str(mock_data.MAX_ACTIVE_HOLDS)
    assert (await client.cancel_hold(SEED_ID))["reply-code"] == "0000"  # seed anulowalny


async def test_ttl_expires_user_holds_but_not_seed(client: OmnisClient, http: httpx.AsyncClient) -> None:
    clock = [datetime(2026, 1, 1, 12, 0, 0)]
    mock_data.set_clock(lambda: clock[0])
    await _place(http, client, "MOCK-SEARCH-A2", ITEM_A2, pickup="MOCKLIB-FD2")
    clock[0] += timedelta(hours=23, minutes=59)
    assert len(await _holds(http, client)) == 2
    clock[0] += timedelta(minutes=2)
    holds = await _holds(http, client)
    assert [h["requestid"] for h in holds] == [SEED_ID]
    assert await _requests_counter(client) == "1"
    clock[0] += timedelta(days=30)
    assert [h["requestid"] for h in await _holds(http, client)] == [SEED_ID]


# --- REQ-H7/H8/H9/H10a: katalog -----------------------------------------------------------------------------------


async def test_pnxs_by_bare_mmsid_returns_exactly_one_record(http: httpx.AsyncClient) -> None:
    for mmsid in ("MOCK-SEARCH-A1", "MOCK-SEARCH-A2", "mock-mms-001"):
        response = await http.get("/primaws/rest/pub/pnxs", params={"q": f"any,contains,{mmsid}", "limit": "10"})
        docs = response.json()["docs"]
        assert len(docs) == 1
        assert docs[0]["pnx"]["control"]["sourcerecordid"] == [mmsid]
    delivery = await http.post("/primaws/rest/pub/delivery", json=["almaMOCK-SEARCH-A1"])
    assert delivery.json()[0]["delivery"]["holding"][0]["holKey"]
    # Prefiks nie jest podciągiem innego id: obcięte id nie trafia w nic.
    assert (await http.get("/primaws/rest/pub/pnxs", params={"q": "any,contains,MOCK-SEARCH-A"})).json()["docs"] == []


async def test_physical_service_exists_for_every_edition(http: httpx.AsyncClient) -> None:
    for mmsid in ("MOCK-SEARCH-A1", "MOCK-SEARCH-A2", "MOCK-SEARCH-B1", "MOCK-SEARCH-C1", "mock-mms-004"):
        response = await http.get(f"/primaws/rest/pub/getPhysicalService/{mmsid}")
        assert response.json() == {"physicalServiceId": f"PS-{mmsid}"}
    assert (await http.get("/primaws/rest/pub/getPhysicalService/nieznany")).status_code == 404


async def test_holdings_items_shape_and_holkey_still_required(http: httpx.AsyncClient) -> None:
    holding = (await http.post("/primaws/rest/pub/delivery", json=["almaMOCK-SEARCH-A1"])).json()[0]["delivery"][
        "holding"
    ][0]
    ok = await http.post("/primaws/rest/priv/ILSServices/holdings/PS-MOCK-SEARCH-A1", json={"locations": [holding]})
    (location,) = ok.json()["data"]["itemInfo"]["locations"]
    assert location["main-location"] == "Filia Demo 1" and location["sub-location"]
    allowed = {i["itemid"]: i["listofservices"]["service"][0]["allowed"] for i in location["items"]}
    assert allowed == {ITEM_A1: "Y", ITEM_A1_READING_ROOM: "N"}
    item = location["items"][0]
    link = item["listofservices"]["service"][0]["link-to-service"]
    assert link.startswith(_item_url("MOCK-SEARCH-A1", ITEM_A1) + "?")  # zgodny z trasą 14
    assert item["listofservices"]["service"][0]["enableWithoutLogin"] is False
    barcodes = [i["itembarcode"] for i in location["items"]]
    assert len(set(barcodes)) == len(barcodes)
    # REQ-18b: bez holKey nadal pusta lista, także dla egzemplarza dostępnego.
    no_key = {k: v for k, v in holding.items() if k != "holKey"}
    empty = await http.post("/primaws/rest/priv/ILSServices/holdings/PS-MOCK-SEARCH-A1", json={"locations": [no_key]})
    assert empty.json() == {"data": {"itemInfo": {"locations": []}}}


# --- Pełny przepływ prawdziwym OmnisClient (wymaga omnis-py z place_hold) -------------------------------------------


@requires_hold_api
async def test_full_hold_flow_via_real_client(client: OmnisClient) -> None:
    items = await client.get_holdable_items("MOCK-SEARCH-A1")
    # `allowed: "N"` (czytelnia) jest pomijany przez klienta.
    assert [i.item_id for i in items] == [ITEM_A1]
    item = items[0]
    assert item.mmsid == "MOCK-SEARCH-A1" and item.main_location == "Filia Demo 1"

    options = await client.get_hold_options(item)
    assert options.request_type == "hold" and options.material_type == "BOOK"
    assert [(p.id, p.type) for p in options.pickup_locations] == [
        ("MOCKLIB-FD1", "LIBRARY"),
        ("MOCKLIB-FD1C", "LIBRARY"),
    ]

    assert await client.get_item_queue(item.item_id) == "(zamówienie: 0)"
    result = await client.place_hold(options, options.pickup_locations[1])
    assert result["status"] == "ok" and "requestid" not in result

    holds = [r.hold for r in await client.get_requests() if r.hold is not None]
    mine = next(h for h in holds if h.mmsid == "MOCK-SEARCH-A1")
    assert mine.available is False and mine.pickup_location == "Filia Demo 1 (czytelnia)"
    assert await _requests_counter(client) == "2"
    assert await client.get_item_queue(item.item_id) == "(zamówienie: 1)"

    await client.cancel_hold(mine.request_id)
    assert [r.hold.request_id for r in await client.get_requests() if r.hold] == [SEED_ID]
    assert await _requests_counter(client) == "1"
    assert await client.get_item_queue(item.item_id) == "(zamówienie: 0)"


@requires_hold_api
async def test_holdable_items_for_loaned_edition_and_branch_filter(client: OmnisClient) -> None:
    """Wypożyczony egzemplarz też można zamówić (kolejka); filtr filii działa po nazwie."""
    items = await client.get_holdable_items("MOCK-SEARCH-A2")
    assert [i.item_id for i in items] == [ITEM_A2]
    assert items[0].status_name and "przekroczon" in items[0].status_name
    assert await client.get_holdable_items("MOCK-SEARCH-A2", branch_filter="nie ma takiej") == []


# --- REQ-H13: jedna edycja, egzemplarze w dwóch filiach ------------------------------------------------------------

MMS_D1 = "MOCK-SEARCH-D1"
ITEM_D1_FD2 = "MOCK-ITEM-MOCK-SEARCH-D1-FD2-1"  # na półce
ITEM_D1_FD3 = "MOCK-ITEM-MOCK-SEARCH-D1-FD3-1"  # wypożyczony
TWO_BRANCH_TITLE = "Latarnicy Szafirowej Zatoki"


async def _d1_holdings(http: httpx.AsyncClient) -> list[dict]:
    delivery = await http.post("/primaws/rest/pub/delivery", json=[f"alma{MMS_D1}"])
    return delivery.json()[0]["delivery"]["holding"]


async def _holdings_for(http: httpx.AsyncClient, holding: dict) -> list[dict]:
    response = await http.post(f"/primaws/rest/priv/ILSServices/holdings/PS-{MMS_D1}", json={"locations": [holding]})
    locations = response.json()["data"]["itemInfo"]["locations"]
    return locations[0]["items"] if locations else []


async def test_two_branch_delivery_and_record_have_two_holdings_with_holkey(http: httpx.AsyncClient) -> None:
    record = (await http.get(f"/primaws/rest/pub/pnxs/L/alma{MMS_D1}")).json()
    for holdings in (await _d1_holdings(http), record["delivery"]["holding"]):
        assert [(h["libraryCode"], h["mainLocation"], h["availabilityStatus"]) for h in holdings] == [
            ("FD2", "Filia Demo 2", "available"),
            ("FD3", "Filia Demo 3", "unavailable"),
        ]
        assert all(h["holKey"] for h in holdings)
        assert len({h["holdId"] for h in holdings}) == 2 and len({h["holKey"] for h in holdings}) == 2


async def test_two_branch_holdings_return_only_items_of_their_own_branch(http: httpx.AsyncClient) -> None:
    fd2, fd3 = await _d1_holdings(http)
    items_fd2, items_fd3 = await _holdings_for(http, fd2), await _holdings_for(http, fd3)
    assert [(i["itemid"], i["mainlocationname"]) for i in items_fd2] == [(ITEM_D1_FD2, "Filia Demo 2")]
    assert [(i["itemid"], i["mainlocationname"]) for i in items_fd3] == [(ITEM_D1_FD3, "Filia Demo 3")]
    assert items_fd2[0]["itemstatusname"] == "Egzemplarz na półce"
    due = (datetime.now() + timedelta(days=8)).strftime("%d/%m/%Y")
    assert items_fd3[0]["itemstatusname"] == f"Wypożyczenie do {due}"
    links = [i["listofservices"]["service"][0]["link-to-service"] for i in (*items_fd2, *items_fd3)]
    assert len(set(links)) == 2 and len({i["itemid"] for i in (*items_fd2, *items_fd3)}) == 2
    assert len({i["itembarcode"] for i in (*items_fd2, *items_fd3)}) == 2
    assert all(i["listofservices"]["service"][0]["allowed"] == "Y" for i in (*items_fd2, *items_fd3))
    for item, other in ((items_fd2[0], fd3), (items_fd3[0], fd2)):
        assert item["mainlocationname"] != other["mainLocation"]


async def test_two_branch_holdings_without_holkey_or_with_foreign_holdid_are_empty(http: httpx.AsyncClient) -> None:
    fd2, fd3 = await _d1_holdings(http)
    assert await _holdings_for(http, {k: v for k, v in fd3.items() if k != "holKey"}) == []
    assert await _holdings_for(http, {**fd3, "holdId": "MOCK-HOLD-OBCY"}) == []
    # `holdId` z innej edycji (A1) też jest obcy; brak `holdId` przy dwóch holdingach nie wskazuje filii.
    assert await _holdings_for(http, {**fd2, "holdId": "MOCK-HOLD-A1"}) == []
    assert await _holdings_for(http, {k: v for k, v in fd2.items() if k != "holdId"}) == []


async def test_two_branch_form_offers_pickup_of_the_items_own_branch(
    client: OmnisClient, http: httpx.AsyncClient
) -> None:
    for item_id, library, name in (
        (ITEM_D1_FD2, "MOCKLIB-FD2", "Filia Demo 2"),
        (ITEM_D1_FD3, "MOCKLIB-FD3", "Filia Demo 3"),
    ):
        response = await http.get(_item_url(MMS_D1, item_id), headers=_auth(client), params={"lang": "pl"})
        group = response.json()["services-arr"]["services"][0]["groups-list-map"][0]
        assert [(p["key"], p["value"]) for p in group["pickupLocation"]] == [(f"{library}$$LIBRARY", name)]
    # Odbiór w filii, której egzemplarz nie ma w formularzu, jest odrzucany.
    wrong = await _place(http, client, MMS_D1, ITEM_D1_FD3, pickup="MOCKLIB-FD2")
    assert wrong.status_code == 400


async def test_two_branch_search_books_via_real_client(client: OmnisClient) -> None:
    """Działa na omnis-py z PyPI: dwie filie z jednej edycji, jedna dostępna, druga z terminem zwrotu."""
    results = await client.search_books(TWO_BRANCH_TITLE)
    assert len(results) == 1 and len(results[0].versions) == 1
    version = results[0].versions[0]
    assert version.mmsid == MMS_D1
    by_name = {b.library_name: b for b in version.branches}
    assert set(by_name) == {"Filia Demo 2", "Filia Demo 3"}
    assert by_name["Filia Demo 2"].status == "available" and by_name["Filia Demo 2"].due_date is None
    assert by_name["Filia Demo 3"].status == "unavailable"
    assert by_name["Filia Demo 3"].due_date == (datetime.now() + timedelta(days=8)).strftime("%d/%m/%Y")
    assert by_name["Filia Demo 3"].overdue is False


@requires_hold_api
async def test_two_branch_holdable_items_and_branch_filter(client: OmnisClient) -> None:
    items = await client.get_holdable_items(MMS_D1)
    assert sorted(i.item_id for i in items) == [ITEM_D1_FD2, ITEM_D1_FD3]
    assert {i.item_id: i.main_location for i in items} == {ITEM_D1_FD2: "Filia Demo 2", ITEM_D1_FD3: "Filia Demo 3"}
    filtered = await client.get_holdable_items(MMS_D1, branch_filter="Demo 3")
    assert [i.item_id for i in filtered] == [ITEM_D1_FD3]


@requires_hold_api
async def test_two_branch_place_hold_affects_only_that_branch_queue(client: OmnisClient) -> None:
    (item,) = await client.get_holdable_items(MMS_D1, branch_filter="Demo 3")
    options = await client.get_hold_options(item)
    assert [p.id for p in options.pickup_locations] == ["MOCKLIB-FD3"]
    assert await client.get_item_queue(ITEM_D1_FD3) == "(zamówienie: 0)"
    await client.place_hold(options, options.pickup_locations[0])

    assert await client.get_item_queue(ITEM_D1_FD3) == "(zamówienie: 1)"
    assert await client.get_item_queue(ITEM_D1_FD2) == "(zamówienie: 0)"
    mine = next(r.hold for r in await client.get_requests() if r.hold and r.hold.mmsid == MMS_D1)
    assert mine.pickup_location == "Filia Demo 3"

    await client.cancel_hold(mine.request_id)
    assert await client.get_item_queue(ITEM_D1_FD3) == "(zamówienie: 0)"
