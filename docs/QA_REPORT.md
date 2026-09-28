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


---

# 2026-09-28 — REQ-G6 — wyszukiwanie po serii + rekord `pnxs/L/alma{mmsid}`

Weryfikacja niezależna (rola `qa`, bez `Write`/`Edit`) zmian niezacommitowanych w chwili weryfikacji
(`git status`/`git diff`: `src/omnis_mock/main.py`, `src/omnis_mock/search_data.py`,
`tests/test_guest_search.py`, `scripts/curl/19_series_search.sh` + dokumentacja). Zakres: REQ-G6 z
`docs/SPEC.md` (pod REQ-G5), zlecenie `omnis-mobile/docs/omnis-mock-guest-search-spec.md` sekcja "REQ-G6",
`docs/DEV_NOTES.md` sekcja "REQ-G6". REQ-G1..G5 (70f41db) nie były re-weryfikowane w tej sesji poza
sprawdzeniem braku regresji (pytest/`run_all.sh`); mają PASS wyżej w tym pliku.

## Metodologia

1. `.venv/bin/pytest -v` → **39/39 PASSED** (5 nowych w `tests/test_guest_search.py`:
   `test_series_search_from_loan_record_finds_all_volumes`, `test_series_search_matches_series_only`,
   `test_record_without_series_and_holding_matches_loan_branch`,
   `test_unknown_record_returns_200_without_pnx`, `test_omnis_py_get_record_details_parses_record`).
2. `.venv/bin/ruff check src tests` → *All checks passed!*; `.venv/bin/black --check src tests` → *All done*
   (10 plików bez zmian).
3. Lokalny serwer (`.venv/bin/uvicorn omnis_mock.main:app --port 8768`, PID zabity po zakończeniu przez
   `kill`, nie `pkill -f`): `BASE_URL=http://localhost:8768 scripts/curl/run_all.sh` → **32 PASS, 0 FAIL**
   (4 nowe asercje REQ-G6 na końcu skryptu); `scripts/curl/19_series_search.sh` ręcznie → output zgodny z
   oczekiwaniami (patrz niżej).
4. Niezależny skrypt `fastapi.testclient.TestClient` (nie część repo, w scratchpadzie sesji) — przechodzi
   pełną ścieżkę `omnis-mobile` (login → `GET loans` → dla KAŻDEGO z 4 wypożyczeń: `GET pnxs/L/alma{mmsid}`
   → emulacja tolerancji parsowania Gson/Kotlin (`toLenientStringListMap`: każda wartość w
   `display`/`addata`/`facets`/`control` musi być prymitywem/listą prymitywów/`null`, nigdy obiektem
   zagnieżdżonym w liście) → emulacja `branchInfoFromHoldings`/`looksLikeAddress` → `seriesSearchTerm`/
   `seriesVolume` → `q=series,contains,...` → `authorSearchTerm` → `q=creator,contains,...`).
5. Czytanie kodu Kotlin (`omnis-mobile`): `OmnisApi.kt::getRecord`, `Models.kt` (`seriesSearchTerm`,
   `seriesVolume`, `authorSearchTerm`, `Pnx`, `Holding`, `RecordResponse`), `BranchInfo.kt`
   (`branchInfoFromHoldings`, `looksLikeAddress`), `OmnisRepository.kt` (`withCatalogDetails`,
   `getBranchInfo`, `searchBooks` — pochodzenie `BookVersion.series`), `LoanComponents.kt`/`SearchScreen.kt`
   (wywołania `onSearch`/`searchFor` z `SearchField.SERIES`). Czytanie `omnis-py`
   (`client.py::get_record_details`, `get_cover_url`, `OmnisClient.__init__`).

## Ścieżka end-to-end per wypożyczenie demo (punkt 3 zlecenia QA — dla KAŻDEGO, nie tylko przykładowego)

| Loan | Tytuł | Parsowanie Kotlin (`Pnx`) | Adres filii (`branchInfoFromHoldings`) | `holKey` | Seria (`seriestitle[0]` → `seriesSearchTerm`/`seriesVolume`) | `series,contains,<term>` | `creator,contains,<authorSearchTerm(au)>` |
|---|---|---|---|---|---|---|---|
| loan-001 | Pan Tadeusz | OK, brak obiektów zagnieżdżonych w listach | `Filia Demo 1` → `ul. Wypożyczeń 1` (rozpoznany jako adres) | obecny | `"Dzieła wszystkie / Adam Mickiewicz ; [t. 4]"` → term `"Dzieła wszystkie"`, tom `4` | `["Dziady", "Pan Tadeusz"]` | `["Dziady", "Pan Tadeusz"]` (zawiera własny tytuł) |
| loan-002 | Lalka | OK | `Filia Demo 2` → `ul. Wypożyczeń 2` (rozpoznany) | obecny | brak serii (`seriestitle: []`) | n/d | `["Lalka"]` |
| loan-003 | Quo Vadis | OK | `Filia Demo 1` → `ul. Wypożyczeń 1` (rozpoznany) | obecny | brak serii | n/d | `["Quo Vadis"]` |
| loan-004 | Dziady | OK | `Filia Demo 3` → `ul. Wypożyczeń 3` (rozpoznany) | obecny | `"Dzieła wszystkie ;  3"` → term `"Dzieła wszystkie"`, tom `3` | `["Dziady", "Pan Tadeusz"]` | `["Dziady", "Pan Tadeusz"]` (zawiera własny tytuł) |

Wszystkie 4 wiersze: `pnx`/`delivery` obecne, żadne pole nie łamie tolerancyjnego parsera Kotlin (Gson przez
`toLenientStringListMap` akceptuje prymityw/listę prymitywów/`null` — sprawdzono, że mock nigdy nie
zagnieżdża obiektu w liście `display`/`addata`/`facets`/`control`), `seriesVolume` daje poprawne numery
tomów (`4` i `3`, dokładnie zgodnie z `[t. 4]` i `; 3` we fixture), `series,contains,...` po obcięciu
zwraca **oba** tomy „Dzieła wszystkie" i **nic więcej**, `creator,contains,...` zawsze zwraca zbiór
zawierający własny tytuł wypożyczenia.

Dodatkowe regresje sprawdzone tym samym `TestClient`:
`any,contains,Kroniki` → `0` (słowo istnieje tylko w `seriestitle` Nibylandii, nie w `any`, REQ-15 bez
zmian); `any,contains,Nibylandii` → `1` (REQ-15 bez regresji); `series,contains,Mickiewicz` → wyłącznie
`["Pan Tadeusz"]` — dopasowanie trafia w odpowiedzialność `"... / Adam Mickiewicz ; ..."` z `seriestitle`
loan-001, ale NIE `"Dzieła wszystkie ;  3"` (loan-004), bo ten zapis serii nie zawiera nazwiska autora —
dokładnie analogiczne do przykładu ze zlecenia („Harry Potter" / „Rowling").

## Weryfikacja zgodności z klientami — REQ-G6

- **`OmnisApi.kt::getRecord`**: `@GET("primaws/rest/pub/pnxs/L/{recordId}")`,
  `@Path("recordId")`, `@Query("vid")`, `@Query("lang") = "pl"`, zwraca `Response<RecordResponse>` —
  dokładnie ścieżka i parametry, które obsługuje `pnxs_record()` w `main.py` (mock ignoruje `vid`/`lang`,
  co jest zgodne z SPEC.md — nie wymaga ich).
- **`RecordResponse`/`Pnx` w Kotlinie**: `Pnx` ma niestandardowy deserializer (`pnxDeserializer`,
  `toLenientStringListMap`) zarejestrowany na `createPrimoGson()`, który jest tą samą instancją `Gson`
  użytą przy tworzeniu klienta Retrofit (`OmnisRepository.createClient`, linia z
  `GsonConverterFactory.create(createPrimoGson())`) — więc `RecordResponse` z `getRecord()` faktycznie
  korzysta z tego samego tolerancyjnego parsera co `PnxDoc` z wyszukiwarki. Potwierdzone dla wszystkich 4
  rekordów wypożyczeń (patrz tabela wyżej) i osobno dla `MOCK-SEARCH-A1`/`MOCK-SEARCH-C1`: żadna wartość w
  `display`/`addata`/`facets`/`control` nie jest obiektem zagnieżdżonym w liście (jedyny przypadek, który
  wywaliłby `asString()` po stronie Kotlina).
- **`seriesSearchTerm`/`seriesVolume`/`authorSearchTerm`** (`Models.kt`) zweryfikowane 1:1 (nie
  reimplementowane od zera po stronie mocka — `_series_search_term` w `tests/test_guest_search.py` i
  `19_series_search.sh` to świadome kopie): dla obu zapisów tomu we fixture (`"... ; [t. 4]"` i
  `"...;  3"`) `seriesSearchTerm` daje identyczny wynik `"Dzieła wszystkie"`, a `seriesVolume` poprawnie
  odróżnia `4` od `3`.
- **`BookVersion.series`** (`OmnisRepository.kt::searchBooks`, ~L788) czyta `v.pnx.addataFirst("seriestitle")`
  — czyli `addata.seriestitle`, NIE `display.series`. To ważne: `_build_pnx()` w mocku ustawia
  `display.series` na `f"{series}$$Q{series}"` (format z linkiem do przeszukiwania, jak w realnym Primo),
  co renderowane wprost jako tekst pokazywałoby użytkownikowi widoczny sufiks `$$Q...`. Sprawdzone, że
  `omnis-mobile` NIGDZIE nie czyta `display.seriestitle`/`display.series` dla tego celu — tylko `addata`,
  która w mocku jest czystym stringiem bez `$$Q`. Brak ryzyka wycieku `$$Q` do UI dla tej ścieżki.
- **`branchInfoFromHoldings`/`looksLikeAddress`** (`BranchInfo.kt`): dopasowanie po
  `mainLocation.trim().equals(wanted, ignoreCase = true)` — potwierdzone dla wszystkich 4 filii demo
  (`Filia Demo 1/2/3`), `subLocation` w formacie `"ul. Wypożyczeń N"` zawsze rozpoznawany przez
  `ADDRESS_MARKER` (prefiks `ul.`).
- **`omnis-py::get_record_details`** parsuje odpowiedź bez wyjątków dla znanego rekordu
  (`isbns`/`publication_date`/`publisher`/`subjects`/`genres`/`physical_description` czytane przez
  `.get(..., [None])[0]`/`.get(..., [])`, tolerancyjnie) — potwierdzone testem
  `test_omnis_py_get_record_details_parses_record` i niezależnie tym samym `TestClient`-em dla
  `MOCK-SEARCH-A1`. **Brak realnego wyjścia do sieci**: `OmnisClient.__init__` (client.py) przy przekazanym
  `client=` ustawia `self.client = client` 1:1 (nie tworzy nowego `httpx.AsyncClient`), więc w testach
  `self.client` to ten sam `httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://mock.local")`
  co reszta testu. `get_cover_url()` woła `self.client.head("https://covers.openlibrary.org/b/isbn/...")`
  — `httpx.AsyncClient` z jednym `transport` kieruje TAM WSZYSTKIE żądania niezależnie od hosta w URL-u
  (transport nie sprawdza hosta), więc to żądanie też trafia do `ASGITransport`→FastAPI, gdzie nie ma
  pasującej trasy → `404` → warunek `response.status_code == 200` w pętli `get_cover_url` jest fałszywy →
  `cover_url = None`. Potwierdzone empirycznie (`test_omnis_py_get_record_details_parses_record` asercja
  `details.cover_url is None`) i przez czytanie kodu — brak realnego zapytania do `covers.openlibrary.org`
  w całym przebiegu testów/QA tej sesji.
- **Nieznany rekord** (`GET pnxs/L/almanieistniejacy`) → `200`, body `{"info": {...}, "facets": [], "docs":
  []}`, klucz `"pnx"` faktycznie NIEOBECNY (nie `null`) — sprawdzone bezpośrednio przez `curl`
  (`19_series_search.sh`) i `assert "pnx" not in body` w teście. `omnis-mobile::withCatalogDetails` traktuje
  `!response.isSuccessful` (nieprawda dla 200) inaczej niż brak `pnx` — kod czyta `response.body()?.pnx`,
  które będzie `null` (Gson zostawia pole domyślne `null` dla `Pnx?`), więc `CatalogDetails(null, null)` —
  zgodne z komentarzem w kodzie „sprawdzone, bez serii".
- **Rekord publiczny, bez tokena**: `GET pnxs/L/alma{mmsid}` bez nagłówka `Authorization` → `200` (sprawdzone
  ręcznie `curl`); z dowolnym (nieznanym) tokenem → również `200`. Zgodne z REQ-G2 (duch, nie dosłowny zakres
  REQ-G2, ale endpoint 11 w SPEC.md wprost mówi "publiczny i nie sprawdza `Authorization`").

## REQ-G6 — REQ po REQ

| REQ | Opis (skrót) | Werdykt | Notatka |
|---|---|---|---|
| REQ-G6 (`q=series,...`) | Case-insensitive substring na CAŁYM `addata.seriestitle` (z tomem i odpowiedzialnością), nie na tytule/autorze; nie wchodzi do `any` | PASS | Sprawdzone dla obu zapisów tomu (`"... / Adam Mickiewicz ; [t. 4]"`, `"... ;  3"`), dla serii z jednym tomem (Nibylandii) i dla braku serii (`[]`). `series,contains,Pan Tadeusz`/`Zmyślak` (słowa z tytułu/autora, nie z serii) → `0`, `any`/`creator` nie łapią frazy z samej serii. |
| REQ-G6 (rekord, znany) | `GET pnxs/L/alma{mmsid}` → `200` z `{"pnx": <ten sam co w wynikach>, "delivery": {"holding": [<z holKey>]}}`, bez tokena | PASS | Potwierdzone dla wszystkich 4 mmsid wypożyczeń demo ORAZ dla 4 edycji z `_WORKS` (A1/A2/B1/C1). `holKey` obecny we wszystkich. `pnx` tolerancyjnie parsowalny przez Kotlinowy `Pnx`/Gson (brak obiektów zagnieżdżonych w listach). |
| REQ-G6 (rekord, nieznany) | `200` z pustą kopertą wyszukiwania, BEZ klucza `pnx` (nie `404`) | PASS | Zweryfikowane, że klucz `"pnx"` faktycznie brakuje (nie `null`) — istotne, bo `response.body()?.pnx` w Kotlinie i `data.get("pnx", {})` w Pythonie oba tolerują brak klucza identycznie jak `null`, więc różnica byłaby niewidoczna dla klientów, ale mock i tak trzyma się litery specyfikacji. |
| Efekt uboczny (`omnis-py`, poza numeracją REQ-G) | `get_record_details`/`omnis-cli --format json/csv` przestają dostawać `404` na tym mocku | PASS | Zweryfikowane niezależnym `TestClient` + testem kontraktowym; brak wyjścia do sieci (łańcuch `OmnisClient.__init__`→`self.client`→wspólny `ASGITransport` opisany wyżej). |

Brak regresji: REQ-14 (`any,contains,Kroniki` → `0`), REQ-15 (`any,contains,Nibylandii` → `1`), REQ-G5
(`creator,contains,...` nadal zawęża do autora, nie łapie serii), REQ-17/18/18b (`holKey` nadal generowany
i wymagany) — wszystkie potwierdzone ponownie w tej sesji, nie tylko odziedziczone z poprzedniego PASS.

## Znaleziska (żadne nie blokuje)

| Znalezisko | Ważność |
|---|---|
| `docs/DEV_NOTES.md` (REQ-G6) twierdzi: "aplikacja zawsze wysyła niezmieniony fragment `seriestitle`". To nie jest ściśle prawdą — `SearchScreen.kt` pozwala użytkownikowi dowolnie edytować `queryInput` (`OutlinedTextField`, L129) PODCZAS gdy aktywne jest `SearchField.SERIES` (chip pozostaje aktywny do jawnego usunięcia „✕"), więc `q=series,contains,<dowolny wpisany tekst>` jest jak najbardziej możliwe, nie tylko kliknięcie „Seria: …". W praktyce nie zmienia to werdyktu — zlecenie i SPEC.md jawnie akceptują substring zamiast dopasowania po słowach jako świadomy kompromis, niezależnie od źródła zapytania. | Informacyjne — do złagodzenia sformułowania w DEV_NOTES.md, nie blokuje. |
| **Niespójność adresu tej samej filii między dwoma źródłami danych, teraz widoczna dzięki REQ-G6**: rekordy pochodzące z `data._LOAN_TEMPLATES` (`_works_from_loans()`) mają `sub_location: "ul. Wypożyczeń N"` dla „Filia Demo N", a ręcznie zdefiniowane edycje w `_EDITIONS_A/B/C` (te same nazwy filii, np. „Filia Demo 1") mają `sub_location: "ul. Testowa 1"`/`"ul. Próbna 2"`/`"ul. Demowa 3"`. Zweryfikowane bezpośrednio: `alma MOCK-SEARCH-A1` → `Filia Demo 1 / ul. Testowa 1`, ale `alma mock-mms-001` (Pan Tadeusz, też Filia Demo 1) → `Filia Demo 1 / ul. Wypożyczeń 1`. Niespójność istnieje od commita `a2023eb` (przed REQ-G6), ale wtedy `pnxs/L/alma{mmsid}` zwracał `404`, więc `getBranchInfo` nigdy nie renderował adresu z rekordu wypożyczenia — REQ-G6 pierwszy raz czyni to widocznym: użytkownik otwierający wypożyczenie zobaczy jeden adres dla „Filia Demo 1", a wynik wyszukiwania katalogu dla tej samej filii — inny. | Niska/informacyjna — dane fikcyjne, żaden REQ w SPEC.md nie wymaga spójności adresu między `_WORKS` a `_works_from_loans()`; nie łamie żadnego assercji klienta (oba formaty przechodzą `looksLikeAddress`). Warto rozważyć ujednolicenie przy najbliższej zmianie fixture, nie blokuje Fazy 4. |
| Real Primo rozróżnia `400` (mmsid w nieprawidłowym formacie) od `200` pustej koperty (nieznany, ale poprawny format) — mock zawsze zwraca `200`, bez względu na format `record_id`. Already jawnie udokumentowane i uzasadnione w `docs/API_FIELDS.md`/`docs/DEV_NOTES.md` ("wszystkie mmsid mocka są nie-numeryczne") — nie jest to ukryte odstępstwo. | Informacyjne, świadoma i udokumentowana decyzja, zgodna z `docs/SPEC.md` (SPEC.md w ogóle nie obiecuje `400` dla tego endpointu). |
| Wcześniejsze zdanie w `CLAUDE.md` ("`omnis-mobile`'s `Holding` nie ma `holKey`") zostało w tym diffie poprawione na aktualne — potwierdzone czytaniem `Models.kt` (`holKey: String? = null` obecne, L329). | Pozytywne — nie jest to nowy problem, odnotowuję jako potwierdzenie, że dokumentacja jest teraz zgodna ze stanem faktycznym. |

## Werdykt końcowy (REQ-G6)

- [x] **PASS** — REQ-G6 (pole `series` w `q` + `GET pnxs/L/alma{mmsid}`) zaimplementowane zgodnie ze
      zleceniem `omnis-mobile/docs/omnis-mock-guest-search-spec.md` i `docs/SPEC.md`, zweryfikowane
      niezależnie dla WSZYSTKICH 4 wypożyczeń demo (nie tylko przykładu z testów dewelopera) oraz przez
      czytanie faktycznego kodu Kotlin/Python klientów (`getRecord`, `seriesSearchTerm`, `seriesVolume`,
      `authorSearchTerm`, `BookVersion.series`, `branchInfoFromHoldings`, `get_record_details`,
      `get_cover_url`). Brak regresji na REQ-1..REQ-G5 (`pytest` 39/39, `run_all.sh` 32/32,
      `19_series_search.sh` zgodny z oczekiwaniami). Ten dodatek NIE zmienia wcześniejszego werdyktu PASS
      dla REQ-G1..G5/Layer 1/Layer 2 — jest z nim zgodny i go rozszerza. Gotowe do Fazy 4 (deploy),
      z zastrzeżeniem dwóch informacyjnych, niskiej wagi znalezisk wyżej (do rozważenia przy okazji, nie
      blokujących).
- [ ] **FAIL** — lista blokujących REQ do zwrotu developerowi: _(brak)_

> **Adnotacja developera po QA (2026-09-28):** znaleziska 1 i 2 poprawione przed commitem. Opis w
> SPEC.md/DEV_NOTES.md mówi teraz, że niezmieniony `seriestitle` wysyła kliknięcie „Seria: …”, a tekst
> może też zostać wpisany ręcznie. Dzieła z wypożyczeń mają adres filii z `_BRANCH_ADDRESS`, taki sam jak
> w `_EDITIONS_A/B/C` („Filia Demo 1” → „ul. Testowa 1” itd.), więc tabela wyżej pokazuje stan sprzed
> poprawki. `pytest` po poprawce: 39/39.

## REQ-L1..REQ-L5 — pełny kształt wypożyczeń + osobna historia — QA (2026-09-28)

**Zakres:** weryfikacja niezacommitowanych zmian w working tree (`git diff` + nowe pliki
`tests/test_loan_details.py`, `scripts/curl/20_loan_history.sh`) wobec zlecenia
`omnis-mobile/docs/omnis-mock-loan-details-spec.md` i przeniesionego do `docs/SPEC.md` kontraktu
(REQ-L1..REQ-L5), decyzje developera w `docs/DEV_NOTES.md` (ostatnia sekcja). QA wykonane bez `Write`/`Edit`
— wyłącznie `Read`/`Bash` (`pytest`, `black`, `ruff`, `curl`, dwa niezależne lokalne serwery `uvicorn`,
czytanie kodu klientów w `omnis-py`, `omnis-mobile`, `omnis-ha`).

### Automatyczne testy

- `.venv/bin/pip install -e ".[dev]"` — OK.
- `.venv/bin/pytest -v` → **48/48 PASS** (39 istniejących + 9 nowych w `tests/test_loan_details.py`,
  w tym `test_omnis_py_parses_active_and_history` — prawdziwy `OmnisClient.get_loans("history")`, zgodny z
  sygnaturą `get_loans(self, loan_type: str = "active")` w zainstalowanym `omnis-py`).
- `.venv/bin/black --check src tests` → czyste (11 plików, w tym nowy `test_loan_details.py`).
- `ruff check src tests` → czyste.
- `bash -n scripts/curl/run_all.sh scripts/curl/20_loan_history.sh` → składnia OK.

### REQ-13/REQ-L5 na długo żyjącej instancji (wymóg #3 zlecenia QA)

Dwa niezależne, świeże lokalne serwery (`.venv/bin/uvicorn omnis_mock.main:app --port <wolny>`, start
w tle, `curl /healthz` w pętli do pierwszej odpowiedzi, zatrzymane po PID — nie `pkill -f`):

- Instancja #1 (port 8017): `run_all.sh` odpalony **4 razy pod rząd** → `35 PASS, 0 FAIL` przy każdym
  uruchomieniu.
- Instancja #2 (port 8018, świeży restart, żeby zobaczyć całą progresję od zera): `run_all.sh` **3 razy
  pod rząd** → `35 PASS, 0 FAIL` każdy raz, a linia REQ-13/REQ-L5 przeszła dokładnie przez trzy gałęzie
  opisane w `DEV_NOTES.md`:
  - run 1: `renew_loan realnie przesuwa duedate (20261003 -> 20261017, Prolongowano)`
  - run 2: `renew_loan realnie przesuwa duedate (20261017 -> 20261031, Prolongowano)`
  - run 3: `renew_loan na limicie maxrenewdate -> bez zmian (20261031, limit 20261031)`

  Zgodne z deklaracją developera („loan-001 mieści dokładnie dwie prolongaty”, „trzeci przebieg przeszedł
  gałęzią na limicie”) — potwierdzone niezależnie, nie tylko odczytane z `DEV_NOTES.md`.

### Ręczna weryfikacja przypadków brzegowych (curl, poza pytest)

| Sprawdzenie | Wynik |
|---|---|
| Złe hasło (`POST /suprimaLogin`) | `401` |
| Brak `Authorization` na `/counters`, `/loans` (GET) | `401` na obu |
| Nieznany `loan_id` w `POST /renew_loans` | `200`, `{"success": true, "renewed": false}` (no-op, zgodnie z REQ-13b) |
| `GET /loans` bez `type` / z `type=bogus` | oba zwracają aktywne (4 pozycje `loan-001..004`) — zgodne z SPEC „każda inna wartość albo jej brak zwraca aktywne” |
| Powtórzone `GET /discovery/search` (3×) | `200` każdorazowo, idempotentne |
| Token gościa (`guestJwt?viewId=...`) na `myaccount/loans?type=history` | `200` z `{"status":"failed","reply-code":"0002",...}` — REQ-G3 rozciąga się poprawnie także na `type=history`, nie tylko `type=active` |
| Pełny dump `GET /loans?type=active` i `?type=history` | zgodne z REQ-L1..L4 co do klucza po kluczu (patrz niżej) |

### REQ-L1..REQ-L5 — REQ po REQ

| REQ | Sprawdzenie | Werdykt |
|---|---|---|
| REQ-L1 | Każdy aktywny `loan` ma wszystkie 13 dodatkowych kluczy (`callnumber2`, `year`, `itemcategorycode`, `itemcategoryname`, `itemstatusname`, `itemid`, `maxrenewdate`, `renewstatuses`, `alerts`, `mainlocationcode`, `secondarylocationcode`, `ilsinstitutioncode`, `nzmmsid`, `nzilsinstitutioncode`); koperta `data.loans` ma `historicloans: "Y"` i `hasAlerts: false` (boolean, nie string) dla **obu** `type`. Zweryfikowane pełnym dumpem JSON i przez `pytest`. | **PASS** |
| REQ-L1 (spójność z katalogiem) | Dla każdego aktywnego loanu: `mainlocationcode` == `holding.libraryCode`, `secondarylocationname` (gdy nie `null`) == `holding.subLocation`, `year` (bez kropki) == `pnx.display.creationdate[0]` rekordu `pnxs/L/alma{mmsid}`. Sprawdzone ręcznie dla `loan-001`/`loan-002` i przez `pytest` dla wszystkich 4. To samo powtórzone dla historii (4/4 `hist-*`, m.in. `MOCK-SEARCH-A1` → `creationdate=2022`/`libraryCode=FD1`/`subLocation=ul. Testowa 1`, zgodne z `year=2022.`/`mainlocationcode=FD1`/`secondarylocationname=ul. Testowa 1`). | **PASS** |
| REQ-L2 | `renewstatuses` w kształcie `{"renewstatus": [...]}` dla odnawialnych (pusta lista, `loan-001`/`loan-002`) i dla nieodnawialnych z DWOMA różnymi powodami: `loan-003` — lista jednoelementowa z tekstem widzianym na żywo; `loan-004` — **goły string** `"Osiągnięto limit prolongat"` zamiast listy (test odporności klienta). Historia poprawnie **nie ma** klucza `renewstatuses` wcale (nie `null`, nieobecny — sprawdzone bezpośrednio w dumpie JSON). | **PASS** |
| REQ-L3 | `loanstatus` ∈ {"Zwykłe","Prolongowano"} (nigdy "Active"); `duehour` = `"2359"` (bez dwukropka) na WSZYSTKICH loanach, aktywnych i historii; `secondarylocationname` = adres filii (`"ul. …"`) w większości, `null` w `loan-003`; `title` z „ / ” w większości (`loan-001/002/003`), bez „ / ” w `loan-004` ("Dziady"). | **PASS** |
| REQ-L4 | `type=history` zwraca 4 pozycje (`hist-001..004`), rozłączne z aktywnymi; `returndate`/`returnhour` obecne, `renewstatuses`/`maxrenewdate`/`alerts` NIEOBECNE; `renew` zawsze `"N"`; `loanstatus` mieszany (`Zwykłe`+`Prolongowano`); `hist-003` ma `itemcategoryname: "Ubytkowany"`, `itemstatusname: "W procesie"`, `secondarylocationname: "Księga ubytków FD1"`; `mmsid` wszystkich 4 pozycji istnieje w katalogu (`pnxs/L/alma{mmsid}` zwraca `pnx`); `showmore` bez `"Y"` (REQ-11 rozciągnięty na historię); `myaccount/counters` liczy tylko aktywne (`Loans` = 4, nie 8). | **PASS** |
| REQ-L5 | Prolongata `loan-001` (`renew:"Y"`) nigdy nie przesuwa `duedate` poza `maxrenewdate` — potwierdzone empirycznie dwoma niezależnymi przebiegami `run_all.sh` (patrz wyżej) i `pytest` (`test_renewal_sets_status_and_respects_maxrenewdate` — 5 kolejnych wywołań `renew_loans` po dojściu do limitu, zawsze `200` no-op, `duedate` bez zmian). Nieodnawialne (`renew:"N"`) są no-opem NIEZALEŻNIE od `maxrenewdate` (sprawdzone kodem: `renew_demo_loan` zwraca `False` już na etapie `tmpl["renew"] != "Y"`, przed sprawdzeniem limitu) — zgodne z `test_non_renewable_loan_does_not_change` i z ręcznym `curl` na `loan-003`. | **PASS** |

### Kompatybilność wsteczna i wielojęzyczna (poza zakresem samego `pytest`)

- **`omnis-py`** (`Loan` pydantic, `client.py`): deklaruje tylko pola z REQ-10 — nowe klucze REQ-L1..L4
  są nadmiarowe i pydantic je ignoruje (potwierdzone przez `test_omnis_py_parses_active_and_history`
  będące realnym `OmnisClient` z PyPI). `due_hour` jest przechowywane i wypisywane w `cli.py` jako
  surowy string (`loan.due_hour`), NIGDZIE nie parsowane jako czas (`grep due_hour` w całym `omnis-py` →
  tylko deklaracja pola + dwa miejsca w tabeli CLI) — zmiana formatu `"23:59"` → `"2359"` **nie** psuje
  `omnis-cli`. `loan.status` również tylko wypisywane, nie porównywane literałowo do `"Active"`.
- **`omnis-ha`**: `grep due_hour/duehour` w `custom_components/omnis` → brak wyników. Sensor/kalendarz
  budują datę tylko z `due_date`, nie z godziny — zmiana formatu godziny jest dla tego projektu
  nieistotna.
- **`omnis-mobile` (Kotlin)**: `Models.kt`/`LoanResponseItem` deklaruje `callnumber2`, `year`,
  `itemcategoryname`, `maxrenewdate`, `renewstatuses` (surowy `JsonElement?`), `returndate`, `returnhour`
  jako **nullable** — Gson zostawia `null` przy braku klucza (historia: brak `maxrenewdate`/`renewstatuses`
  → `null`; aktywne: brak `returndate`/`returnhour` → `null`), zero `NullPointerException`/wyjątku
  deserializacji. `renewStatusMessages()` (Models.kt) obsługuje explicité oba kształty `renewstatuses`
  (obiekt z listą ORAZ obiekt z gołym stringiem) — dokładnie to, co generuje `loan-003`/`loan-004`.
  `isRegularLoanStatus()` (Models.kt L202-205) już traktuje `"zwykłe"` (case-insensitive) jako status
  regularny równolegle z `"active"`/`"normal"`/`"aktywne"` — apka była już przygotowana na zmianę
  `"Active"` → `"Zwykłe"` PRZED tą sesją mocka, więc karta wypożyczenia nie zacznie fałszywie pokazywać
  badge'a statusu. `displayTitle()` (Models.kt L191-198) to dokładnie ta funkcja, którą
  `tests/test_loan_details.py::_display_title` kopiuje — potwierdzone czytaniem źródła, nie tylko
  deklaracją w komentarzu testu.
- **Historia — paginacja w Kotlinie (`OmnisRepository.getLoanHistoryPage`, `OmnisViewModel` L728-820)**:
  `hasMore` liczone WYŁĄCZNIE z `"Y" in showmore` (nigdy z `size == bulk` ani domyślnie `true` po
  pierwszej stronie) i `HistoryCursor(nextOffset, hasMore)` gate'uje kolejne wywołania
  (`if (!cursor.hasMore) return@forEach`). Mock zwraca `showmore: []` dla historii przy każdym
  wywołaniu, więc `hasMore=false` po pierwszej stronie — aplikacja **nie** poprosi o drugą stronę i nie
  zduplikuje 4 pozycji historii na ekranie. Brak błędu.
- **`loan-004` (zmiana `renew: "Y"` → `"N"`)**: `grep -rn "loan-004"` w całym workspace poza
  `omnis-mock/` → brak wyników — żaden inny projekt nie hardkoduje tego identyfikatora ani nie zakłada
  jego wcześniejszej odnawialności. Zmiana jest bezpieczna.

### Dane osobowe / prawdziwe identyfikatory (wymóg #6)

Rozszerzony grep na `git diff` + oba nowe, nieśledzone pliki (`tests/test_loan_details.py`,
`scripts/curl/20_loan_history.sh`) — wzorce: adres filii ze zlecenia (`Osinowa`), kody lokalizacji/
instytucji z realnej odpowiedzi (`F08`, `FIL08`, `48OMNIS*`, `BRACZ`, `BRP`), długie numery (Alma
mmsid/itemid, ≥15 cyfr) oraz literalne przykładowe ID ze zlecenia (`23123456780009337`,
`99123456780009336`, `48OMNIS_NETWORK`) — **żadnego trafienia**. Wszystkie identyfikatory w mocku są
własnym schematem (`MOCK-ITEM-…`, `MOCK-NZ-…`, `MOCK`, `MOCK_NETWORK`, `FD1`/`FD1dz`), zgodnie z deklaracją
w `DEV_NOTES.md` („Identyfikatory celowo mockowe, bez kopiowania przykładowych numerów ze zlecenia”).
`itemcategorycode: "WZ_30"` i etykieta „Wypożyczane na 30 dni” są skopiowane ze zlecenia dosłownie, ale to
kod kategorii egzemplarza (metadane biblioteczne, nie dane osobowe/identyfikujące) — bez zastrzeżeń.

### Dokumentacja (wymóg #7)

- `docs/SPEC.md` (endpoint 4/5, „Dane demo”), `CLAUDE.md`, `docs/DEV_NOTES.md`,
  `scripts/curl/README.md` — zgodne z kodem punkt po punkcie (sprawdzone wyżej), bez sprzecznych
  przykładów (REQ-10 w SPEC.md nie zawiera już nieaktualnego przykładu `"23:59"`/`"Active"` — jest
  odniesieniem ogólnym, nie konkretną wartością).
- **Znalezisko (informacyjne, niebronujące)**: sekcja „Kryterium akceptacji — PRIMARY oracle” w
  `docs/SPEC.md` opisuje osobno oracle dla Layer 1, Layer 2 i REQ-G1..REQ-G6, ale nie wspomina
  `tests/test_loan_details.py` jako oracle dla REQ-L1..REQ-L5 (mimo że ten plik realnie jest tym oracle —
  zawiera `test_omnis_py_parses_active_and_history` z prawdziwym `OmnisClient`). Nie wpływa na
  poprawność implementacji, tylko na kompletność tej jednej sekcji dokumentu — do uzupełnienia przy
  najbliższej okazji.

### Werdykt końcowy (REQ-L1..REQ-L5)

- [x] **PASS** — REQ-L1..REQ-L5 zaimplementowane zgodnie ze zleceniem
      `omnis-mobile/docs/omnis-mock-loan-details-spec.md` i `docs/SPEC.md`, zweryfikowane niezależnie:
      `pytest` 48/48, `black`/`ruff` czyste, `run_all.sh` 0 FAIL na dwóch niezależnych, świeżo
      wystartowanych lokalnych instancjach (4× i 3× pod rząd, w tym pełna progresja normalna →
      no-op-na-limicie zgodna z deklaracją developera), ręczne `curl` na przypadkach brzegowych spoza
      `pytest` (złe hasło, brak `Authorization`, nieznany `loan_id`, `type=bogus`, token gościa na
      `type=history`), spójność wypożyczeń z katalogiem (kody lokalizacji, adresy, rok) dla WSZYSTKICH
      4 aktywnych i 4 historycznych pozycji (nie tylko przykładu z testów dewelopera), oraz czytanie
      faktycznego kodu klientów (`omnis-py`, `omnis-ha`, `omnis-mobile`/Kotlin) — brak regresji, brak
      danych osobowych/prawdziwych identyfikatorów w diffie. Jedyne znalezisko to niebronująca,
      informacyjna niekompletność jednego akapitu dokumentacji (patrz wyżej). Gotowe do Fazy 4 (deploy).
- [ ] **FAIL** — lista blokujących REQ do zwrotu developerowi: _(brak)_
