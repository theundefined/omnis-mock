# scripts/curl/

Gotowe skrypty `curl` do ręcznego eksplorowania i testowania API `omnis-mock`, po jednym na endpoint/REQ
z [`../../docs/SPEC.md`](../../docs/SPEC.md) (nazwy plików odpowiadają numeracji REQ z tego dokumentu), plus
`run_all.sh` uruchamiający wszystko po kolei z podsumowaniem PASS/FAIL.

Nie zastępują `tests/test_contract.py` (ten uruchamia prawdziwy `OmnisClient` z `omnis-py` — silniejszy
kontrakt, patrz `docs/SPEC.md` "Kryterium akceptacji"). Te skrypty są od czegoś innego: szybkiego,
zależnego-tylko-od-`curl`/`python3` sprawdzenia bez instalowania niczego — przydatne zwłaszcza przeciwko
żywemu deployowi na Render, gdzie `pytest` się nie odpala.

## Użycie

```bash
# przeciwko lokalnemu serwerowi deweloperskiemu (domyślne BASE_URL)
uvicorn omnis_mock.main:app --reload &
./01_health.sh
./03_login_success.sh
./06_loans.sh
./07_renew_loan.sh loan-002
./run_all.sh

# przeciwko żywemu deployowi
BASE_URL=https://omnis-mock.onrender.com ./run_all.sh
```

`BASE_URL`/`DEMO_USERNAME`/`DEMO_PASSWORD` to zmienne środowiskowe (patrz `lib.sh`) — domyślne wartości
pasują do lokalnego serwera z domyślną konfiguracją z `.env.example`.

## Pliki

| Skrypt | REQ (SPEC.md) | Co sprawdza |
|---|---|---|
| `01_health.sh` | — | `/healthz` |
| `02_discovery_search.sh` | REQ-2 | cookie-priming, bez auth |
| `03_login_success.sh` | REQ-3, REQ-4 | poprawne logowanie, dekoduje payload JWT |
| `04_login_invalid_credentials.sh` | REQ-1 | złe dane logowania → 401 |
| `05_counters.sh` | REQ-5, REQ-6, REQ-7 | stan konta |
| `06_loans.sh` | REQ-8, REQ-9, REQ-10, REQ-11 | lista wypożyczeń |
| `07_renew_loan.sh [loan_id]` | REQ-12, REQ-13 | prolongata — **mutuje stan** (patrz nagłówek pliku) |
| `08_renew_unknown_loan.sh` | REQ-13b | prolongata nieznanego id → 200 no-op |
| `09_unauthenticated_requests.sh` | REQ-5, REQ-8, REQ-12 | brak `Authorization` → 401 |
| `10_catalog_search_stub.sh` | REQ-14 | niepasujące zapytanie → `{"docs": []}` |
| `11_catalog_search_match.sh` | REQ-15, REQ-16 | trafiające zapytanie + group expansion (`qInclude`) |
| `12_catalog_search_delivery.sh` | REQ-17 | dostępność per filia, pełny `holding` z `holKey` |
| `13_get_physical_service.sh` | REQ-18 | id usługi fizycznej; nieznany mmsid → 404 |
| `14_ils_holdings.sh` | REQ-18b | termin zwrotu — z `holKey` vs bez (pusta odpowiedź, nie 404) |
| `run_all.sh` | wszystkie powyższe | pełny przebieg z podsumowaniem PASS/FAIL |
