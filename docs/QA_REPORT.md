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

---

# Dodatek: 2026-09-28 — REQ-G1..REQ-G5 (anonimowe wyszukiwanie tokenem gościa + wyszukiwanie po autorze)

Weryfikacja niezależna, zgodnie z zasadą QA z góry tego dokumentu: werdykt PASS/FAIL per REQ, niezależny od
zielonego `pytest`. Zmiany niezacommitowane w momencie weryfikacji (`git status`/`git diff`). Źródła prawdy
użyte: `omnis-mobile/docs/omnis-mock-guest-search-spec.md` (oryginalne zlecenie), `docs/SPEC.md` (sekcja
"Anonimowe wyszukiwanie...", endpoint 10, zmieniona sekcja 9, "Dane katalogu"), `docs/DEV_NOTES.md`
(sekcja REQ-G1..REQ-G5).

## Wynik `pytest -v`

Uruchomione z `.venv/bin/pytest -v` po `.venv/bin/python -m pip install -e ".[dev]"`:

```
34 passed in 0.79s
```

Wszystkie 6 testów `tests/test_contract.py` (kontrakt QA, NIE zmieniany w tej sesji) nadal PASS —
niezmienione. `tests/test_search_contract.py` (7 testów, jedna asercja zmieniona: `result.author ==
"Nibylska, Karolina"` zamiast `"Karolina Nibylska"`, konsekwencja zmiany formatu `addata.au` — zgodne z
opisanym w DEV_NOTES.md powodem, nie osłabienie testu) PASS. Nowy `tests/test_guest_search.py` (17 testów)
PASS.

`.venv/bin/python -m ruff check src tests` → `All checks passed!`. `.venv/bin/black --check src tests` →
`10 files would be left unchanged.` Oba czyste.

## Scenariusz akceptacyjny ze zlecenia (kroki 1–6), lokalny uvicorn (port 8766)

`BASE_URL=http://localhost:8766 scripts/curl/run_all.sh` → **28 PASS, 0 FAIL** (włącznie z 14 sprawdzeniami
Layer 1/Layer 2 sprzed tej sesji — bez regresji). Skrypty `15_guest_jwt.sh`..`18_guest_myaccount_denied.sh`
uruchomione osobno, wyniki dosłowne poniżej.

### Krok 1–4 (pipeline `pnxs`→`delivery`→`getPhysicalService`→`ILSServices/holdings` tokenem gościa)

```
1. GET /primaws/rest/pub/pnxs?q=any,contains,Nibylandii&scope=MyInstitution&... (Authorization: Bearer <guest>)
   -> almaMOCK-SEARCH-A1 | Cienie Nibylandii | Nibylska, Karolina

2. POST /primaws/rest/pub/delivery ["almaMOCK-SEARCH-A2"]
   -> availabilityStatus: unavailable
   -> holKey: HoldingResultKey [mid=MOCK-HOLD-A2, libraryId=MOCK-LIB-FD2, locationCode=FD2dz, callNumber=null]

3. GET /primaws/rest/pub/getPhysicalService/MOCK-SEARCH-A2
   -> physicalServiceId: PS-MOCK-SEARCH-A2

4. POST /primaws/rest/priv/ILSServices/holdings/PS-MOCK-SEARCH-A2 (Authorization: Bearer <guest>, holding z kroku 2)
   -> HTTP 200
   -> {"data":{"itemInfo":{"locations":[{"items":[{"itemstatusname":"Wypożyczony - termin zwrotu przekroczony od 23/09/2026"}]}]}}}
```

Zgodne dosłownie ze scenariuszem ze zlecenia.

### Krok 5 (wyszukiwanie po autorze, `q=creator,contains,...`)

```
addata.au z wyniku 'Nibylandii': Nibylska, Karolina

q=creator,contains,Nibylska, Karolina    -> ['Cienie Nibylandii']
q=creator,contains,Cienie                -> []
q=any,contains,Cienie                    -> ['Cienie Nibylandii']
q=creator,contains,Mickiewicz, Adam      -> ['Pan Tadeusz', 'Dziady']
```

Wartość z przecinkiem trafia do tego samego rekordu (dowód, że `q` dzieli się tylko na dwóch pierwszych
przecinkach), pole `creator` poprawnie NIE dopasowuje słowa z tytułu, `any` dalej dopasowuje tytuł+autora,
autor z dwoma dziełami zwraca oba.

### Krok 6 (`myaccount/loans` tokenem gościa)

```
GET /primaws/rest/priv/myaccount/loans (Authorization: Bearer <guest>)
-> HTTP 200
-> {"beaconO22":"0","status":"failed","reply-code":"0002","reply-text":"The patron ID is invalid","data":null}
```

Zgodne dosłownie z REQ-G3 — **200, nie 401**. Sprawdzono też `counters` i `renew_loans` tokenem gościa —
identyczne body, 200, w każdym przypadku.

## Ręczne testy edge case poza `tests/test_guest_search.py` i skryptami curl

Wszystkie na lokalnym uvicornie (port 8766), niezależnie od skryptów dostarczonych przez developera:

- **`Content-Type` `guestJwt`**: nagłówek odpowiedzi dokładnie `content-type: application/json;charset=UTF-8`
  (sprawdzone `curl -i`), zgodnie z REQ-G1 — nie `application/json` bez charsetu, co dałby domyślny
  `JSONResponse`.
- **Non-ASCII w `viewId`/`institution`**: `institution=Łódź` (URL-encoded), `viewId=Wid√ok:Zażółć` →
  token wydany, payload zdekodowany standardowym `base64.b64decode` daje poprawny JSON z `\uXXXX`
  escape'ami, `json.loads` → `{"institution": "Łódź", "viewId": "Wid√ok:Zażółć", ...}` — payload jest
  czystym ASCII i bezstratnie dekodowalny, zgodnie z wymogiem REQ-G1/REQ-4.
- **Kodowanie base64 tokena gościa**: zdekodowano wszystkie 3 segmenty (`header`, `payload`, `signature`)
  standardowym `base64.b64decode` z doklejonym paddingiem — wszystkie 3 dekodują się bez błędu do sensownego
  JSON/bajtów, zgodnie ze standardowym (nie urlsafe) alfabetem z REQ-4.
- **`language` domyślne**: brak `lang` w query → payload ma `"language": "en"`, zgodnie z próbką
  prawdziwego tokena w zleceniu.
- **Token gościa / token z logowania / nieznany token / brak nagłówka na 4 endpointach wyszukiwarki**
  (`pnxs`, `delivery`, `getPhysicalService`, `ILSServices/holdings`): wszystkie kombinacje → `200` —
  nagłówek `Authorization` jest w pełni ignorowany, zgodnie z REQ-G2 (włącznie z opcjonalnym punktem
  zlecenia "działa też bez nagłówka wcale", świadomie wdrożonym).
- **Token z logowania na `myaccount/*`** (kontrolne, nie REQ-G): `GET /loans` z tokenem z logowania →
  `200` z realnymi 4 loanami — potwierdza, że `_require_patron` nie zepsuł ścieżki z prawdziwym tokenem.
- **`Authorization: authorization: bearer <guest_token>`** (małe litery `bearer`) na `myaccount/loans` →
  `401` (nie 200 z `"failed"`) — token z małym `bearer` nie jest rozpoznawany jako `Bearer <token>` wcale
  (zgodne z istniejącą ścisłością z Layer 1 QA, `is_valid_token`/`token_kind` sprawdzają `startswith("Bearer ")`
  dosłownie), więc trafia w gałąź "nieznany token" → 401, zgodnie z REQ-G3 ("Brak tokena albo nieznany
  token → 401 jak dotąd").
- **`renew_loans` tokenem gościa nie mutuje stanu**: potwierdzone też niezależnie od
  `test_guest_renew_does_not_mutate_loans` — `_require_patron` zwraca odpowiedź "failed" PRZED
  `data.renew_demo_loan()`, więc funkcja mutująca nie jest wołana. Kod widziany bezpośrednio w `main.py`
  (`renew_loans`: `if (denied := _require_patron(request)) is not None: return denied` — wcześniej niż
  `body = await request.json()` / `data.renew_demo_loan(loan_id)`).
- **`q` z wieloma przecinkami**: `q=creator,contains,Nibylska, Karolina, extra, stuff` → `[]` (wartość po
  drugim przecinku to `"Nibylska, Karolina, extra, stuff"`, nie jest substringiem znormalizowanego autora)
  — zachowanie zgodne z opisanym "dzieli TYLKO na dwóch pierwszych przecinkach", nie błąd.
- **`q` bez prefiksu pola** (`q=Nibylandii`, bez `,contains,`): traktowane jako `("any", "Nibylandii")` →
  1 wynik. `q` z jednym przecinkiem (`q=any,Nibylandii`) → `[]` (poprawnie, bo `_parse_q` wymaga DWÓCH
  przecinków, żeby rozpoznać `pole,operator,wartość`; z jednym przecinkiem cała wartość `"any,Nibylandii"`
  jest traktowana jako fraza `any`, więc dopasowanie substring nie trafia — zgodne z kodem, nie błąd).
- **REQ-14 nadal trzyma**: `q=any,contains,cokolwiek-xyz-nonsense` → `{"docs": []}`.
- **Nieznane pole w `q`** (`q=title,contains,Cienie`): zachowuje się jak `any` (dopasowuje tytuł) —
  zgodne z SPEC.md ("nieznane pole — zachowanie dowolne, np. jak `any`").
- **`scope=` (pusty string)** → `200` (traktowany jak brak parametru, zgodnie z decyzją opisaną w
  DEV_NOTES.md — nie jest to w SPEC.md dosłownie, ale nie jest odstępstwem, bo SPEC.md nie definiuje
  zachowania dla pustego stringa, tylko dla "brak parametru" i "nieznana wartość").
- **`400` dla nieznanego `scope`**: `curl -i` → `HTTP/1.1 400 Bad Request`, `content-length: 0` — body
  faktycznie puste (nie `{"detail": ...}` jak dałby domyślny `HTTPException`), zgodnie z "wierność"
  zleconą opcjonalnie i zaimplementowaną.
- **Wielokrotne `/discovery/search`**: 3 kolejne wywołania → `200 200 200`, bez efektów pobocznych.
- **Kompatybilność wsteczna**: `scope=MyInstitution2` (omnis-py, starsze omnis-mobile) → `200`, tak jak
  `scope=MyInstitution`; `q=any,contains,...` (format omnis-py) działa niezmiennie.
- **Wyszukiwanie po autorze case-insensitive, z polskimi znakami diakrytycznymi**: `creator,contains,prus`,
  `creator,contains,BOLESŁAW PRUS`, `creator,contains,Sienkiewicz, Henryk` — wszystkie trafiają poprawnie
  (`Lalka`, `Lalka`, `Quo Vadis`).

## Weryfikacja zgodności z klientami (omnis-py, omnis-mobile) — punkt 4 zlecenia QA

- **`omnis-py`** (`src/omnis/client.py`): `_addata_first(doc, "au")` czyta `addata.au` jako zwykły string
  bez założeń o formacie (brak parsowania na `aulast`/`aufirst` po stronie klienta — `grep` potwierdza brak
  użycia tych pól w `omnis-py` w ogóle). Zmiana formatu `au` z `"Karolina Nibylska"` na `"Nibylska,
  Karolina"` nie psuje niczego strukturalnie — `SearchResult.author` po prostu zmienia treść (stąd zmieniona
  asercja w `tests/test_search_contract.py`, prawidłowo, nie osłabienie testu).
- **`omnis-mobile`** (Kotlin): `Pnx.addataFirst("au")` (`Models.kt`) analogicznie — string bez
  transformacji. `SearchScreen.kt` (`onAuthorClick(author)`, linia ok. 573) przekazuje `result.author`
  (czyli `addataFirst("au")`) **1:1, bez trymowania/dzielenia po przecinku**, do
  `searchFor(query, SearchField.AUTHOR)` → `viewModel.runSearch` → `OmnisRepository.searchBooks(field=
  SearchField.AUTHOR)` → `"q" to "${field.primoField},contains,$q"` = `"creator,contains,Nibylska,
  Karolina"` (`OmnisRepository.kt` ~L585). Zweryfikowano bezpośrednio w kodzie Kotlin (nie zgadywane): to,
  co aplikacja faktycznie wysyła po kliknięciu autora, **dokładnie trafia** w kontrakt `_parse_q`
  (podział tylko na dwóch pierwszych przecinkach) zaimplementowany w mocku. Brak transformacji (bez
  cudzysłowów, bez `$$Q`, bez podziału na `;`) — sprawdzone czytając `SearchScreen.kt` L555–580 i
  `OmnisRepository.kt` L540–600.
- **`scope`**: `omnis-mobile` (`OmnisRepository.kt` L594) wysyła `"scope" to "MyInstitution"` (nowa
  wersja); `omnis-py` (`client.py` L466) wysyła `"scope": "MyInstitution2"`. Oba zaakceptowane przez mock
  (`_KNOWN_SCOPES = {"MyInstitution", "MyInstitution2"}`) — zgodne.
- **`guestJwt`**: `omnis-mobile`'s `OmnisApi.getGuestJwt` (Retrofit) wysyła `institution` jako `@Path`,
  `viewId`/`targetUrl`/`isGuest`/`lang` jako `@Query` — dokładnie sygnatura, którą obsługuje
  `guest_jwt()` w `main.py`. Body odbierane jako `ResponseBody` (nie model), `.string()?.trim()?.trim('"')`
  — zgodne z tym, że mock zwraca literał stringu JSON, nie obiekt.
- **Obserwacja poboczna (nie blokuje, informacyjna, nie część REQ-G1..G5)**: `CLAUDE.md` (część niezmieniona
  w tym diffie) zawiera zdanie "`omnis-mobile`'s `data class Holding` (Kotlin) dziś **nie ma pola
  `holKey`**". Sprawdzono bezpośrednio w kodzie (`omnis-mobile/app/src/main/kotlin/.../model/Models.kt`,
  `data class Holding`) — pole `holKey: String? = null` **już istnieje** i jest przekazywane 1:1 przez
  `HoldingsStatusRequest.locations: List<Holding>`. To zdanie w `CLAUDE.md` jest więc nieaktualne (dobra
  wiadomość: krok 4 scenariusza akceptacyjnego rozwiązuje się nie tylko dla `omnis-py`, ale też dla
  prawdziwej aplikacji `omnis-mobile`). Nie jest to regresja wprowadzona w tej sesji (plik nie był
  edytowany w tym miejscu) — zgłaszam jako drobną poprawkę do wprowadzenia przy najbliższej okazji, nie
  jako FAIL.

## REQ-G1..REQ-G5 — REQ po REQ

| REQ | Opis (skrót) | Werdykt | Notatka |
|---|---|---|---|
| REQ-G1 | `GET guestJwt` → `200`, string JSON w cudzysłowach, `Content-Type` z charsetem, token 3-segmentowy z payloadem GUEST; brak `viewId` → `400` puste body | PASS | Zweryfikowano dosłowny nagłówek `content-type: application/json;charset=UTF-8`, payload z non-ASCII input (`Łódź`) poprawnie ASCII-escapowany i dekodowalny standardowym `b64decode`. `language` domyślnie `"en"` przy braku `lang`. |
| REQ-G2 | `pnxs`/`delivery`/`getPhysicalService`/`ILSServices/holdings` działają z tokenem gościa, tokenem z logowania, nieznanym tokenem i bez nagłówka | PASS | Wszystkie 4×4 kombinacje sprawdzone ręcznie → `200`. Pułapka `holKey` (REQ-18b) nadal działa z tokenem gościa (potwierdzone przez `test_full_search_pipeline_with_guest_token_via_real_client` — asercja na `due_date`, nie tylko `len(results)`). |
| REQ-G3 | Token gościa na `myaccount/loans`/`counters`/`renew_loans` → `200` z dokładnym body `"status":"failed","reply-code":"0002"`, NIE 401; brak/nieznany token → 401 bez zmian; `renew_loans` nie mutuje stanu | PASS | Body zweryfikowane bajt-po-bajcie curlem, zgodne 1:1 ze zleceniem. `renew_loans` guest-tokenem potwierdzone jako no-op na `duedate` (zarówno testem jak i przez czytanie kodu — `_require_patron` zwraca wcześniej niż `renew_demo_loan()`). Lowercase `bearer` poprawnie wpada w gałąź 401 (nieznany token), nie w gałąź "guest". |
| REQ-G4 | `scope` akceptuje `MyInstitution`/`MyInstitution2`/brak, nieznany → `400` z pustym body; `tab` ignorowany; `delivery` nie waliduje `scope` | PASS | `400` ma `content-length: 0` (nie `{"detail":...}`), zgodnie z "wierność". `scope=` (pusty string) → `200`, decyzja z DEV_NOTES.md, nie odstępstwo od SPEC.md (SPEC.md nie definiuje tego przypadku dosłownie). |
| REQ-G5 | `q` parsowane jako `pole,operator,wartość` z podziałem tylko na 2 pierwszych przecinkach; `creator` dopasowuje tylko autora; `any`/nieznane pole — tytuł+autor; dopasowanie w obu zapisach autora | PASS | Zweryfikowano wartość z przecinkiem (`"Nibylska, Karolina"`) end-to-end, `creator` nie łapie słowa z tytułu, autor z dwoma dziełami zwraca oba, case-insensitive z polskimi znakami diakrytycznymi. Potwierdzone też, że `omnis-mobile` faktycznie wysyła `au` 1:1 z przecinkiem (czytanie kodu Kotlin) — nie tylko teoretyczna zgodność kształtu. |

Dodatkowo zweryfikowano brak regresji na REQ-14 (dowolne nietrafiające zapytanie → `{"docs": []}`) oraz na
REQ-15/16/17/18/18b (pojedyncze zapytanie, `qInclude`, `delivery`, `getPhysicalService`, pułapka `holKey`)
— wszystkie nadal PASS w `run_all.sh` (28/28) i `pytest`.

## Znaleziska (żadne nie blokujące)

| Znalezisko | Ważność |
|---|---|
| Zmieniona asercja w `tests/test_search_contract.py` (`author == "Nibylska, Karolina"`) | Informacyjne — konsekwencja zaakceptowanej zmiany formatu `au`, nie osłabienie testu. |
| `q=title,contains,...` (nieznane pole) traktowane jak `any` | Zgodne z zezwoleniem w zleceniu ("zachowanie dowolne"). |
| `scope` sprawdzany case-sensitive (`myinstitution` ≠ `MyInstitution`) | Informacyjne, SPEC.md nie wymaga inaczej. |
| `bearer` małymi literami z tokenem gościa → `401`, nie gałąź "guest" | Zgodne z istniejącą ścisłością `startswith("Bearer ")` z Layer 1 (REQ-5), nie nowy defekt. |
| Token z logowania + całkowicie pusty body na `renew_loans` → `500` (nieobsłużony `JSONDecodeError`) | Pre-istniejące, nieruszone w tej sesji (już odnotowane w PASS dla Layer 1 wyżej w tym pliku). Ścieżka z tokenem gościa nie dotyka tego kodu wcale — `_require_patron` odcina wcześniej. |
| `userName`/`user` gościa budowane z `datetime.now()` (czas lokalny procesu), a `iat`/`exp` z `time.time()` (epoch UTC) | Kosmetyczne — brak wpływu na kontrakt, żaden klient nie parsuje `userName` jako daty. |
| `CLAUDE.md` (fragment nieedytowany w tej sesji) twierdzi, że `omnis-mobile`'s `Holding` nie ma `holKey` — nieaktualne, pole już istnieje i jest przekazywane 1:1 | Informacyjne, drobna poprawka dokumentacji do wprowadzenia przy okazji — nie dotyczy zmian z tej sesji i nie blokuje. |
| Rejestr tokenów gościa (`_guest_tokens`) to kolejny nieograniczony set in-memory, tej samej klasy ryzyka jak `_valid_tokens` (już odnotowane dla Fazy 4/deploy w sekcji Layer 1 wyżej) | Informacyjne, nie nowa klasa ryzyka. |

## Werdykt końcowy (REQ-G1..REQ-G5)

- [x] **PASS** — REQ-G1..REQ-G5 zgodne ze zleceniem `omnis-mobile/docs/omnis-mock-guest-search-spec.md` i
      `docs/SPEC.md`; brak regresji na REQ-1..REQ-18b (Layer 1/Layer 2 bez zmian zachowania, `pytest`
      34/34, `run_all.sh` 28/28). Ten dodatek NIE zmienia wcześniejszego werdyktu PASS dla Layer 1
      (Faza 4/deploy) — jest z nim zgodny i go rozszerza.
- [ ] **FAIL** — lista blokujących REQ do zwrotu developerowi: _(brak)_
