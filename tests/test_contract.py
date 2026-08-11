"""Kontraktowy test end-to-end: prawdziwy `OmnisClient` z opublikowanej paczki `omnis-py` (PyPI, deklarowany
jako dev-dependency w pyproject.toml) uruchomiony przeciwko tej aplikacji FastAPI w procesie (przez
`httpx.ASGITransport` — bez prawdziwego portu sieciowego).

To jest GŁÓWNE kryterium akceptacji QA (docs/SPEC.md, sekcja "Kryterium akceptacji"; docs/PLAN.md, Faza 2).
Silniejsze niż ręcznie pisane assercje, bo korzysta z prawdziwych modeli Pydantic klienta: jeśli `OmnisClient`
nie rzuci `ValidationError` ani nieobsłużonego wyjątku HTTP, kontrakt się trzyma.

NIE mockuj tu `omnis.client` — sensem tego pliku jest właśnie to, że nic w nim nie jest mockiem poza samym
serwerem, który testujemy. NIE edytuj tego pliku w roli `developer` — to kontrakt QA (patrz
`.claude/agents/developer.md`).

Ten plik jest celowo czerwony, dopóki `src/omnis_mock/{main,auth,data}.py` nie zostaną zaimplementowane
(Faza 1 z docs/PLAN.md) — to jest oczekiwane i jest to definicja "gotowe" dla developera: doprowadzić do
zielonego stanu bez zmiany tego pliku.
"""

from collections.abc import AsyncIterator

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
    """Deterministyczny stan przed KAŻDYM testem — renew_loan w jednym teście nie może przeciekać do innego."""
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


async def test_invalid_credentials_return_401(client: OmnisClient) -> None:
    """SPEC.md REQ-1: złe dane logowania -> dokładnie 401, co omnis-py zamienia na ten konkretny ValueError."""
    with pytest.raises(ValueError, match="Invalid credentials"):
        await client.login("not-the-demo-user", "wrong-password", institution=INSTITUTION, view=VIEW)


async def test_full_demo_cycle_matches_omnis_py_contract(client: OmnisClient) -> None:
    """Login -> user_info -> loans -> renew_loan, bez ValidationError ani wyjątków HTTP.

    To jest dokładnie scenariusz opisany w docs/SPEC.md jako PRIMARY oracle.
    """
    await client.login(mock_data.DEMO_USERNAME, mock_data.DEMO_PASSWORD, institution=INSTITUTION, view=VIEW)

    info = await client.get_user_info()
    assert info.display_name
    assert info.user_name
    assert info.loans_count >= 1

    loans = await client.get_loans()
    assert len(loans) >= 1

    # SPEC.md "Dane demo": fixture musi mieć oba stany renewable.
    assert any(loan.renewable for loan in loans), "SPEC.md wymaga >=1 wypożyczenia z renew='Y' w fixture"
    assert any(not loan.renewable for loan in loans), "SPEC.md wymaga >=1 wypożyczenia z renew='N' w fixture"

    renewable_loan = next(loan for loan in loans if loan.renewable)
    due_date_before = renewable_loan.due_date

    await client.renew_loan(renewable_loan.id)

    loans_after = await client.get_loans()
    updated_loan = next(loan for loan in loans_after if loan.id == renewable_loan.id)
    assert updated_loan.due_date != due_date_before, "SPEC.md REQ-13: renew_loan musi realnie przesunąć termin"


async def test_loans_dataset_has_overdue_item(client: OmnisClient) -> None:
    """SPEC.md 'Dane demo': co najmniej jedno wypożyczenie musi być przeterminowane (duedate < dziś)."""
    from datetime import date

    await client.login(mock_data.DEMO_USERNAME, mock_data.DEMO_PASSWORD, institution=INSTITUTION, view=VIEW)
    loans = await client.get_loans()

    today = date.today().strftime("%Y%m%d")
    assert any(loan.due_date < today for loan in loans), "SPEC.md wymaga >=1 przeterminowanego wypożyczenia"


async def test_loans_pagination_terminates(client: OmnisClient) -> None:
    """SPEC.md REQ-11 (pułapka): showmore=['Y'] przy fixture < 50 pozycji zawiesza omnis-py w nieskończonej
    pętli HTTP. Ten test z definicji nie zawiśnie tylko jeśli fixture jest poprawny — timeout = FAIL.
    """
    await client.login(mock_data.DEMO_USERNAME, mock_data.DEMO_PASSWORD, institution=INSTITUTION, view=VIEW)
    loans = await client.get_loans()
    assert len(loans) < 50


async def test_renew_unknown_loan_id_does_not_error(client: OmnisClient) -> None:
    """SPEC.md REQ-13b: nieznany loan_id -> 200 no-op, nie wyjątek."""
    await client.login(mock_data.DEMO_USERNAME, mock_data.DEMO_PASSWORD, institution=INSTITUTION, view=VIEW)
    await client.renew_loan("nonexistent-loan-id")  # nie powinno rzucić httpx.HTTPStatusError


async def test_catalog_search_stub_returns_empty_results(client: OmnisClient) -> None:
    """SPEC.md REQ-14: /pnxs to bezpiecznik dla SearchScreen w omnis-mobile, nie pełny mock (Layer 2)."""
    await client.login(mock_data.DEMO_USERNAME, mock_data.DEMO_PASSWORD, institution=INSTITUTION, view=VIEW)
    results = await client.search_books("cokolwiek", fetch_due_dates=False)
    assert results == []
