# QA_REPORT.md

Wypełnia subagent `qa` w Fazie 2 (i ewentualnie Fazie 3) z `docs/PLAN.md`. Werdykt per REQ z `docs/SPEC.md`
— PASS/FAIL/N-A, i dla każdego FAIL: dokładny request + otrzymana odpowiedź (nie samo "nie działa").

**Zasada:** zielony `pytest` to podłoga, nie sufit. Werdykt tutaj jest niezależny od wyniku testów — jeśli
implementacja odbiega od SPEC.md w czymś, co test nie sprawdza dosłownie, to i tak FAIL.

## Wynik `pytest -v`

Uruchomione niezależnie po `pip install -e ".[dev]"` (świeży reinstall, `omnis-py==0.2.10` z PyPI):

```
tests/test_contract.py::test_invalid_credentials_return_401 PASSED       [ 16%]
tests/test_contract.py::test_full_demo_cycle_matches_omnis_py_contract PASSED [ 33%]
tests/test_contract.py::test_loans_dataset_has_overdue_item PASSED       [ 50%]
tests/test_contract.py::test_loans_pagination_terminates PASSED          [ 66%]
tests/test_contract.py::test_renew_unknown_loan_id_does_not_error PASSED [ 83%]
tests/test_contract.py::test_catalog_search_stub_returns_empty_results PASSED [100%]

============================== 6 passed in 0.62s ===============================
```

Zielony, 6/6. `ruff check src` i `black --check src` — również czyste (potwierdzone niezależnie, nie tylko
wg `DEV_NOTES.md`).

Dodatkowo przejrzano źródło `omnis-py==0.2.10` (`venv/lib/python3.12/site-packages/omnis/client.py`)
bezpośrednio, żeby zweryfikować twierdzenia SPEC.md o zachowaniu klienta (401-special-case w `login()`,
dokładnie 10 wymaganych pól `Loan`, `while True` w `get_loans()`, `float(fines_str)` w `get_user_info()`,
brak walidacji kształtu w `renew_loan()`) — wszystkie zgodne z opisem w SPEC.md.

Przejrzano też `src/omnis_mock/{main,auth,data}.py` pod kątem sekcji "Bezpieczeństwo / ograniczenia"
w SPEC.md (brak REQ-numeru, ale to część kontraktu): brak jakichkolwiek importów `httpx`/`requests`/innego
klienta HTTP w tych trzech plikach — potwierdzone, mock nie robi żadnych wywołań wychodzących do
prawdziwego Primo/OpenLibrary/innego API. Zgodne.

## Layer 1 — REQ po REQ

| REQ | Opis (skrót) | Werdykt | Notatka |
|---|---|---|---|
| REQ-1 | złe dane logowania → 401 | PASS | Zweryfikowano 3 warianty: złe hasło, złe login, puste body — wszystkie dokładnie `401`. |
| REQ-2 | `GET /discovery/search` → 200, bez auth | PASS | `curl` bez nagłówka Authorization → `200`. |
| REQ-3 | poprawne dane → `{"jwtData": ...}` | PASS | Body dokładnie `{"jwtData": "<token>"}`. |
| REQ-4 | token: 3 segmenty, payload ASCII z displayName/userName | PASS | Token ma dokładnie 2 kropki (3 segmenty). Payload zdekodowany ręcznie (standardowy base64 + padding): `{"displayName": "Demo User", "userName": "demo"}` — czysty ASCII. Nośnikiem dowodu na pułapkę #1 (standardowy, nie urlsafe, alfabet) jest lektura `auth.py` (`base64.b64encode`, jawnie standardowy alfabet, skomentowane dlaczego) — sam brak `-`/`_` w tym konkretnym tokenie jest wynikiem zerojedynkowym dla tego payloadu (nie zawiera bajtów, które akurat wymagałyby `+`/`/` ani ich urlsafe odpowiedników), więc nie jest samodzielnym dowodem; traktuj go jako potwierdzenie zgodne z kodem, nie zamiennik przeczytania kodu. |
| REQ-5 | `/counters` bez tokena → 401 | PASS | Także sprawdzono: brak prefiksu `Bearer`, `Bearer ` z pustym tokenem, `bearer` małymi literami, losowy token — wszystkie `401`. |
| REQ-6 | `/counters` kształt odpowiedzi | PASS | `{"data":{"listofactions":{"action":[...]}}}` dokładnie zgodny ze SPEC.md, `Loans` = `"4"` zgodnie z liczbą loanów w fixture. |
| REQ-7 | `/counters` Fines format `"0.00"` (kropka) | PASS | `{"type":"Fines","value":"0.00"}` — kropka, nie przecinek. |
| REQ-8 | `/loans` bez tokena → 401 | PASS | |
| REQ-9 | `/loans` kształt odpowiedzi | PASS | `{"data":{"loans":{"loan":[...],"showmore":[]}}}` dokładnie zgodny. |
| REQ-10 | każdy loan ma 10 wymaganych pól + `renew` | PASS | Wszystkie 4 loany w fixture mają wszystkie 10 wymaganych kluczy jako string (`loanid`, `mmsid`, `title`, `duedate`, `duehour`, `loandate`, `loanstatus`, `ilsinstitutionname`, `mainlocationname`, `itembarcode`), plus `author` (string), `secondarylocationname: null` (dozwolone) i `renew` ("Y"/"N"). Daty w formacie `YYYYMMDD`. |
| REQ-11 | `showmore` nie zawiesza paginacji przy < 50 rekordach | PASS | `showmore` zawsze `[]` w `main.py` (hardkodowane), fixture ma 4 loany — `omnis-py`'s pętla `while` kończy się natychmiast. Zgodne z `test_loans_pagination_terminates`. |
| REQ-12 | `/renew_loans` bez tokena → 401 | PASS | |
| REQ-13 | znany `id` → 200 + realna mutacja `duedate` | PASS | Zmierzono ręcznie: `loan-001` przed `renew`: `duedate=20260816`, po jednym wywołaniu `POST /renew_loans`: `duedate=20260830` — dokładnie +14 dni. |
| REQ-13b | nieznany `id` → 200 no-op (nie 404/500) | PASS | `{"id":"totally-bogus-id-xyz"}` → `200 OK`, `{"success":true,"renewed":false}`. |
| REQ-14 | `/pnxs` zawsze `{"docs": []}` | PASS | Sprawdzono z dowolnymi query params, z tokenem i bez — zawsze dokładnie `{"docs":[]}`. |

## Ręczne testy edge case (poza `tests/test_contract.py`)

- **Złe hasło → dokładny status**: `POST /primaws/suprimaLogin?lang=pl` z `username=demo&password=WRONGPASS`
  → `HTTP/1.1 401 Unauthorized`, body `{"detail":"Invalid credentials"}`. Dodatkowo sprawdzono złe
  `username` (poprawne hasło) i całkowicie puste body formularza — oba również `401`.
- **Nieznany `loan_id` w `renew_loans` → dokładny status**: `POST /primaws/rest/priv/myaccount/renew_loans?lang=pl`
  z ważnym tokenem i body `{"id":"totally-bogus-id-xyz"}` → `HTTP/1.1 200 OK`, body
  `{"success":true,"renewed":false}`. Zgodne z REQ-13b (no-op, nie błąd).
- **Brak nagłówka `Authorization` na `/counters`/`/loans`/`/renew_loans`**: wszystkie trzy → dokładnie
  `401 Unauthorized`. Dodatkowo dla `/counters` sprawdzono warianty: nagłówek `Authorization: Bearer `
  (pusty token) → `401`; `authorization: bearer <token>` (małe litery, nagłówek HTTP jest
  case-insensitive z natury, ale wartość `bearer` zamiast `Bearer` już nie) → `401`, ponieważ
  `is_valid_token()` w `auth.py` sprawdza `startswith("Bearer ")` z wielkiej litery — zgodne z tym, jak
  prawdziwy klient (`omnis-py`) zawsze wysyła nagłówek (`f"Bearer {self.token}"`, zawsze wielka litera), więc
  to nie blokuje kontraktu, ale warto odnotować jako świadomą (nie przypadkową) ścisłość.

### Dodatkowa obserwacja (nie blokuje PASS, poza zakresem jakiegokolwiek REQ)

`POST /primaws/rest/priv/myaccount/renew_loans?lang=pl` z ważnym tokenem, ale **całkowicie pustym body**
(brak `-d`, `Content-Length: 0`) zwraca `HTTP/1.1 500 Internal Server Error` (`json.decoder.JSONDecodeError`
w `request.json()`, nieobsłużone w `main.py`) zamiast granicznie eleganckiej odpowiedzi. Żaden REQ w
SPEC.md tego nie wymaga — `omnis-py`'s `renew_loan()` zawsze wysyła poprawny JSON (`json={"id": loan_id}`),
więc PRIMARY oracle (kontrakt z prawdziwym klientem) nie jest tym dotknięty i test to nie wykrywa. Ponieważ
mock ma docelowo być publicznie dostępny (recenzent Google Play, potencjalnie inne boty/skanery), warto to
rozważyć jako drobne utwardzenie w przyszłej iteracji (np. `try/except` wokół `request.json()` →
`HTTPException(400)`), ale to nie jest odstępstwo od `docs/SPEC.md` i nie blokuje tej fazy.

### Obserwacja dot. Fazy 4 (devops/deploy) — nie blokuje PASS tutaj, ale warto przekazać dalej

`auth._valid_tokens` to zbiór **modułowy, in-memory, per proces**. SPEC.md jawnie błogosławi stan
in-memory resetowany restartem ("Restart procesu resetuje wszystko do stanu początkowego... zamierzone,
nie luka") — ale to zdanie w SPEC.md dotyczy dosłownie `_renewal_extensions` (prolongaty), nie rejestru
tokenów. Efekt restartu dla rejestru tokenów jest ostrzejszy: klient trzymający wcześniej wydany token
dostanie `401` na `/counters`/`/loans`/`/renew_loans` po dowolnym restarcie procesu, nie tylko "zresetowane
dane demo". Sprawdzono `Dockerfile`: `CMD uvicorn ... --host 0.0.0.0 --port ${PORT:-8000}` — brak flagi
`--workers`, czyli **pojedynczy proces/worker** — to wyklucza gorszy wariant (token wydany przez worker A,
sprawdzany przez worker B → losowe 401 nawet bez restartu). Z jednym workerem ryzyko ogranicza się do
"Render (darmowy tier) usypia po bezczynności" — już odnotowanego w `CLAUDE.md` jako pułapka do
zweryfikowania w Fazie 4. To nie jest odstępstwo od `docs/SPEC.md` i nie zmienia werdyktu, ale devops
powinien to mieć na uwadze przy konfiguracji Render (nie dodawać `--workers 2+` bez jednoczesnej zmiany
rejestru tokenów na coś odpornego na restart/wielo-workerowość).

### Dodatkowa obserwacja #2 (nie blokuje PASS, zgodne z literą REQ-13)

`renew_demo_loan()` w `data.py` nie sprawdza pola `renew` szablonu — `POST /renew_loans` z
`{"id":"loan-003"}` (loan z `renew: "N"` w fixture) faktycznie przesuwa `duedate` o +14 dni, mimo że
klient (`omnis-py`/`omnis-mobile`) nie powinien nigdy zaproponować renew dla takiego loanu w UI. REQ-13
mówi dosłownie "znany `id` → 200 + mutacja", bez zastrzeżenia o `renew: "N"`, więc to zgodne z literą
specyfikacji — odnotowuję to jako obserwację, nie FAIL.

## Werdykt końcowy

- [x] **PASS** — gotowe do Fazy 4 (devops/deploy)
- [ ] **FAIL** — lista blokujących REQ do zwrotu developerowi: _(brak — wszystkie REQ-1..REQ-14 PASS)_
