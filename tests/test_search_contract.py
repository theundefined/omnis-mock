"""Kontraktowy test end-to-end dla Layer 2 (wyszukiwarka katalogu) — tej samej klasy co
`tests/test_contract.py`: prawdziwy `OmnisClient` z opublikowanej paczki `omnis-py` (PyPI) uruchomiony
przeciwko tej aplikacji FastAPI w procesie (`httpx.ASGITransport`).

NIE edytuję `tests/test_contract.py` — to kontrakt QA (zakaz edycji przez rolę `developer`, patrz
`omnis-mock/CLAUDE.md`). Istniejący `test_catalog_search_stub_returns_empty_results` w tamtym pliku (REQ-14,
zapytanie "cokolwiek") musi przejść bez zmian — dowód, że dopasowanie w Layer 2 zostało świadomie zawężone
(patrz `search_data.search()`), nie że wyszukiwarka nadal jest bezpiecznikiem.

Kontrakt: docs/SPEC.md REQ-14..REQ-18b. Pełna lista pól per endpoint: docs/API_FIELDS.md.
"""

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


@pytest.fixture(autouse=True)
def _reset_mock_state() -> None:
    mock_data.reset_state()
    mock_auth.reset_state()
    yield
    mock_data.reset_state()
    mock_auth.reset_state()


@pytest.fixture
async def client() -> AsyncIterator[OmnisClient]:
    transport = httpx.ASGITransport(app=app)
    http_client = httpx.AsyncClient(transport=transport, base_url="http://mock.local")
    omnis_client = OmnisClient(base_url="http://mock.local", client=http_client)
    yield omnis_client
    await omnis_client.close()


async def _login(client: OmnisClient) -> None:
    await client.login(mock_data.DEMO_USERNAME, mock_data.DEMO_PASSWORD, institution=INSTITUTION, view=VIEW)


async def test_search_groups_versions_and_resolves_due_dates(client: OmnisClient) -> None:
    """SPEC.md REQ-15/REQ-16/REQ-17: "Cienie Nibylandii" ma 2 wydania (frbrgroupid=MOCK-GROUP-A) — group
    expansion musi je oba zwrócić, z dostępnością per filia z `delivery`.
    """
    await _login(client)
    results = await client.search_books("Nibylandii")

    assert len(results) == 1
    result = results[0]
    assert result.title == "Cienie Nibylandii"
    assert result.author == "Karolina Nibylska"
    assert len(result.versions) == 2

    by_mmsid = {v.mmsid: v for v in result.versions}
    available = by_mmsid["MOCK-SEARCH-A1"]
    assert available.edition == "Wydanie II poprawione"
    assert available.branches[0].status == "available"
    assert available.branches[0].library_name == "Filia Demo 1"
    assert available.branches[0].sub_location == "ul. Testowa 1"
    assert available.branches[0].maps_url == "https://maps.app.goo.gl/mockA1"
    assert available.branches[0].due_date is None


async def test_search_unavailable_overdue_branch_resolves_via_holkey(client: OmnisClient) -> None:
    """SPEC.md REQ-18b: termin zwrotu dla niedostępnej wersji rozwiązuje się WYŁĄCZNIE dzięki temu, że
    `holding.holKey` z `delivery` wraca 1:1 w żądaniu do `ILSServices/holdings` — jeśli mock zgubi/nie
    doda `holKey`, ten test czerwienieje (due_date zostanie None), zamiast fałszywie przejść przez sam
    fakt niepustej listy wyników (patrz uzasadnienie w planie: `len(results) > 0` nic tu nie dowodzi).
    """
    await _login(client)
    results = await client.search_books("Nibylandii")
    unavailable = next(v for v in results[0].versions if v.mmsid == "MOCK-SEARCH-A2")

    assert unavailable.edition == "Wydanie I"
    branch = unavailable.branches[0]
    assert branch.status == "unavailable"

    expected_due = (date.today() + timedelta(days=-5)).strftime("%d/%m/%Y")
    assert branch.due_date == expected_due
    assert branch.overdue is True


async def test_search_future_due_date_is_not_overdue(client: OmnisClient) -> None:
    """SPEC.md REQ-18b: "Biblioteka Za Mgłą" ma termin w przyszłości -> overdue=False (druga gałąź reguły
    "przekroczon" w itemstatusname, dopełniająca scenariusz przeterminowany z testu powyżej).
    """
    await _login(client)
    results = await client.search_books("Biblioteka Za Mgłą")

    assert len(results) == 1
    branch = results[0].versions[0].branches[0]
    assert branch.status == "unavailable"

    expected_due = (date.today() + timedelta(days=12)).strftime("%d/%m/%Y")
    assert branch.due_date == expected_due
    assert branch.overdue is False


async def test_search_available_single_edition_skips_due_date_enrichment(client: OmnisClient) -> None:
    """ "Ostatni Rejs Wyobraźni" jest w całości dostępny — klient nie odpala łańcucha
    getPhysicalService/ILSServices dla dostępnych gałęzi (SPEC.md REQ-18), więc due_date musi zostać None.
    """
    await _login(client)
    results = await client.search_books("Rejs Wyobraźni")

    assert len(results) == 1
    assert len(results[0].versions) == 1
    branch = results[0].versions[0].branches[0]
    assert branch.status == "available"
    assert branch.due_date is None


async def test_search_unmatched_query_returns_empty(client: OmnisClient) -> None:
    """Regresja lokalna dla dopasowania świadomie zawężonego do substring "{title} {author}" (SPEC.md
    REQ-15) — musi zostać pusty dla frazy niepasującej do żadnego z 3 fikcyjnych dzieł, tak samo jak
    REQ-14 wymaga tego dla `tests/test_contract.py::test_catalog_search_stub_returns_empty_results`.
    """
    await _login(client)
    results = await client.search_books("kompletnie nieznana fraza xyz", fetch_due_dates=False)
    assert results == []


async def test_ils_holdings_without_holkey_returns_empty_not_404(client: OmnisClient) -> None:
    """SPEC.md REQ-18b, sprawdzone bezpośrednio (bez przechodzenia przez cały search_books): body bez
    `holKey` w `locations[0]` -> 200 z pustą listą `items`, replikując empirycznie zweryfikowane
    zachowanie realnego Primo (omnis-mobile/docs/api-verification-response.md), NIE 404.
    """
    await _login(client)
    response = await client.client.post(
        "/primaws/rest/priv/ILSServices/holdings/PS-MOCK-SEARCH-A2",
        headers={"Authorization": f"Bearer {client.token}"},
        json={
            "filters": {"noItem": 10, "sublibrary": "Filia Demo 2", "holid": "MOCK-HOLD-A2"},
            "locations": [{"mainLocation": "Filia Demo 2", "holdId": "MOCK-HOLD-A2"}],
            "hideResourceSharing": False,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"data": {"itemInfo": {"locations": []}}}
