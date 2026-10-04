# DEV_NOTES.md

## Faza 1 (Layer 1)

- Data: 2026-08-11
- Zaimplementowano bezpośrednio w tej samej sesji, która pisała `docs/SPEC.md` (nie przez osobnego
  subagenta `developer`) — z tego powodu poniższe notatki są bardziej szczegółowe niż typowy handoff, bo
  obejmują też to, co formalna Faza 2 (`qa`) normalnie by wyłapała niezależnie.
- Decyzje niejednoznaczne w SPEC.md i jak zostały rozstrzygnięte:
  - **Znaleziony i naprawiony błąd w samym SPEC.md REQ-4**: specyfikacja pierwotnie dopuszczała kodowanie
    JWT payloadu jako "standard lub urlsafe base64". To błąd — `omnis-py` dekoduje przez zwykłe
    `base64.b64decode()`, które przy `validate=False` (domyślne) po cichu odrzuca znaki `-`/`_` zamiast
    rzucić błąd. Naprawione w SPEC.md i w `auth.py` (`_b64_encode_no_pad` używa `base64.b64encode`,
    standardowego alfabetu, jawnie skomentowane dlaczego).
  - `check_credentials`/`issue_token`: `displayName` ustawiony na stałe `"Demo User"` (nie z env var) —
    SPEC.md tego nie rozstrzygał wprost, ale wymóg ASCII-only + brak potrzeby konfigurowalności uzasadnia
    stałą wartość.
- Odstępstwa od SPEC.md: brak. Wszystkie REQ-1..REQ-14 zaimplementowane dosłownie wg opisu.
- **Znaleziony brak w samym SPEC.md** (nie w implementacji): `GET /primaws/rest/pub/pnxs/L/alma{mmsid}`
  (`get_record_details`) nie był wymieniony na liście "poza zakresem Layer 1", mimo że `omnis-cli --format
  json/csv` go woła. Dopisane do SPEC.md z wyjaśnieniem, że brak tego endpointu to czysta degradacja
  (per-konto `"error"` w wyniku), nie crash — zweryfikowane manualnie, patrz "Manualne testy" niżej.
- Cokolwiek, co QA powinien wiedzieć przed weryfikacją: **formalna, niezależna Faza 2 (rola `qa`) NIE była
  jeszcze uruchomiona jako osobny subagent.** To, co niżej, to testy wykonane przez tę samą sesję, która
  pisała kod — nie zastępuje niezależnej weryfikacji z `docs/QA_REPORT.md`.

## Wykonane testy (poza formalną Fazą 2)

- `pytest -v` — 6/6 zielone (`tests/test_contract.py`, prawdziwy `OmnisClient` z PyPI przez ASGITransport).
- `ruff check src` — czyste. `black --check src` — czyste (po jednym auto-reformacie `auth.py`).
- Manualnie, lokalnym serwerem (`uvicorn`, port 8000) + prawdziwym `omnis-cli` z izolowanym `HOME`
  (żeby nie dotknąć prawdziwego `~/.config/omnis-py/config.yaml` użytkownika):
  - domyślny widok tabelaryczny — poprawny, wypożyczenia pogrupowane wg filii, przeterminowana pozycja
    poprawnie oznaczona.
  - `--renew` — realnie przesuwa `duedate` (+14 dni za każde wywołanie, zweryfikowane przez log serwera:
    3 wywołania `POST /renew_loans` dla 3 loanów z `renew: "Y"`, 0 dla `renew: "N"`).
  - `--format json` — ujawnił brak `get_record_details` (patrz wyżej), obsłużony gracefully przez
    `omnis-py` (`error` per konto, nie crash całego polecenia).

## Faza 3 (Layer 2, jeśli realizowana)

_(nie realizowana w tej sesji)_

## REQ-G1..REQ-G5 — anonimowe wyszukiwanie (token gościa) + wyszukiwanie po autorze

- Data: 2026-09-28
- Źródło: zlecenie `omnis-mobile/docs/omnis-mock-guest-search-spec.md`, przeniesione do `docs/SPEC.md`
  (sekcja „Anonimowe wyszukiwanie”, endpoint 10). Implementacja w sesji głównej, bez osobnego subagenta
  `developer`.
- Opcjonalne punkty zlecenia wdrożone po decyzji użytkownika:
  - wyszukiwarka bez tokena, łącznie z `priv/ILSServices/holdings`, który ignoruje `Authorization`;
  - nieznany `scope` → `400` z pustym body;
  - format autora w katalogu „Nazwisko, Imię” w `au`/`addau`/`sort.author`/`contributor`.
- Decyzje niejednoznaczne w zleceniu i jak zostały rozstrzygnięte:
  - Pusty `scope=` jest traktowany jak brak parametru, a nie jako nieznany scope.
  - `guestJwt` zwraca 400 tylko przy braku `viewId`. Brak `isGuest`/`lang`/`targetUrl` jest tolerowany.
    `language` w payloadzie pochodzi z `lang`, a przy jego braku ma wartość `"en"`, jak w próbce
    prawdziwego tokena.
  - Wypożyczenia (`data.py`) zostają z autorem w kolejności naturalnej. Zlecenie mówiło tylko o
    `addata.au`, a zmiana w wypożyczeniach nie byłaby nigdzie sprawdzalna.
  - Dopasowanie `any`/`creator` normalizuje przecinki i białe znaki i patrzy na obie formy autora. Dzięki
    temu „Weir, Andy” i „Weir Andy” dają to samo, tak jak w prawdziwym Primo, a REQ-14 („cokolwiek” →
    pusto) nadal przechodzi.
  - Rejestr tokenów gościa to osobny set in-memory, tak jak tokeny z logowania. Rośnie bez limitu między
    restartami. Tak samo jest już dla tokenów z logowania, a dane demo są publiczne, więc nie jest to nowa
    klasa ryzyka.
- Zmieniona asercja w `tests/test_search_contract.py`: `result.author == "Nibylska, Karolina"`, jako
  konsekwencja zmiany formatu `au`. `tests/test_contract.py` (kontrakt QA) nie był ruszany.
- Wykonane testy: `pytest` 34/34 (w tym nowy `tests/test_guest_search.py`), `ruff`/`black` czyste,
  `scripts/curl/run_all.sh` na lokalnym uvicornie 28/28 PASS, skrypty 15–18 uruchomione ręcznie.
- **Weryfikacja na żywym Primo (2026-09-28)**: anonimowo, tokenem gościa, bez żadnych danych konta, na
  Bibliotece Raczyńskich (`48OMNIS_BRP:BRACZ`) i Dolnośląskiej Bibliotece Publicznej
  (`48OMNIS_WBP:48OMNIS_WBP`). Dla obu tenantów zgodne z mockiem:
  - `guestJwt` bez parametrów → 400 z pustym body; z parametrami → 200,
    `application/json;charset=UTF-8`, token w cudzysłowach, payload `anonymous-…`/`GUEST`/`displayName:
    null`.
  - `myaccount/loans`, `counters` i `renew_loans` tokenem gościa → 200 z dokładnie tym samym body
    `"reply-code":"0002"`. Zachowanie `renew_loans`, w zleceniu nieprzetestowane, jest teraz potwierdzone.
  - `pnxs`: `scope=MyInstitution` → 200, nieznany scope → 400 z pustym body. Działa bez tokena i z
    nieznanym tokenem.
  - `creator,contains,Prus, Bolesław` i `creator,contains,Prus Bolesław` dają ten sam wynik (262 w BRACZ,
    151 w DBP), `au` ma format „Nazwisko, Imię”.
  - `ILSServices/holdings` → termin zwrotu zarówno z tokenem gościa, jak i bez tokena.

  Różnice między tenantami, które mock świadomie upraszcza:
  - Bez `holKey` BRACZ zwraca pustą listę (REQ-18b), a DBP mimo to zwraca termin zwrotu. Mock odwzorowuje
    BRACZ.
  - `creator,contains,Lalka` → w BRACZ 0 wyników, w DBP 25 rekordów bez `au` (prawdopodobnie dopasowanie
    po innym polu twórcy). Mock dopasowuje `creator` wyłącznie do autora.

  Skrypt weryfikacyjny nie jest w repo, bo robi ruch do prawdziwych bibliotek. Jego odtworzenie to ~100
  linii `httpx` według kroków ze scenariusza akceptacyjnego zlecenia.

## REQ-G6 — wyszukiwanie po serii + rekord `pnxs/L/alma{mmsid}`

- Data: 2026-09-28
- Źródło: to samo zlecenie z `omnis-mobile`, rozszerzone tego samego dnia (`omnis-mobile` v0.6.1 dodał
  wyszukiwanie po serii, v0.6.2 pobiera serię i autora wypożyczeń z rekordu katalogu).
- Weryfikacja na żywym Primo przed implementacją (BRACZ, token gościa):
  - `series,contains,Harry Potter` = 30, bez względu na wielkość liter i kolejność słów.
  - `series,contains,Rowling` = 16, czyli dopasowanie obejmuje odpowiedzialność w `seriestitle`.
  - Rekord → 200 `{…, pnx, delivery{holding}, …}`.
  - Nieznany numeryczny mmsid → 200 z pustą kopertą wyszukiwania bez `pnx`; mmsid w nieprawidłowym formacie
    → 400.
- Decyzje:
  - Seria dla wypożyczeń: „Pan Tadeusz” i „Dziady” (oba z wypożyczeń demo, ten sam autor) w serii
    „Dzieła wszystkie”, z dwoma różnymi zapisami tomu. Nowe dzieło (np. drugi tom Nibylandii) zmieniłoby
    liczbę wyników `any,contains,Nibylandii`, od której zależą istniejące testy i skrypty.
  - `series` dopasowuje substring (jak zlecenie), a nie wszystkie słowa (jak prawdziwe Primo). Kliknięcie
    „Seria: …” wysyła niezmieniony fragment `seriestitle`. Ręcznie wpisany tekst w trybie SERIES (pole da
    się edytować w `SearchScreen`) może w mocku znaleźć mniej niż w Primo, np. przy odwróconej kolejności
    słów.
  - Nieznany rekord zwraca pustą kopertę bez `pnx`. Nie ma 400 dla „złego formatu”, bo mmsid mocka są
    nie-numeryczne.
- Efekt uboczny: `omnis-py` `get_record_details` (i `omnis-cli --format json/csv`) przestaje dostawać
  `404`. Test `test_omnis_py_get_record_details_parses_record` to sprawdza.
- Testy: `pytest` 39/39, `ruff`/`black` czyste, `run_all.sh` lokalnie 32/32, `19_series_search.sh`
  uruchomiony ręcznie.

## REQ-L1..REQ-L5 — pełny kształt wypożyczeń + osobna historia

- Data: 2026-09-28
- Źródło: `omnis-mobile/docs/omnis-mock-loan-details-spec.md` (okno „Szczegóły wypożyczenia”, kształt z
  odpowiedzi na żywo z Raczyńskich), przeniesione do `docs/SPEC.md` (endpointy 4 i 5, „Dane demo”).
  Implementacja w sesji głównej.
- Opcjonalne punkty zlecenia wdrożone oba: goły string w `renewstatus` (REQ-L2) i limit `maxrenewdate`
  (REQ-L5).
- Decyzje:
  - Tytuł: nowe pole `loan_title` w `_LOAN_TEMPLATES`. `title` zostaje krótkim tytułem dzieła dla katalogu,
    więc wyszukiwarka, serie i istniejące testy się nie zmieniają. `tests/test_guest_search.py` szuka
    wypożyczeń po `loanid` zamiast po tytule.
  - „Dziady” (`loan-004`) zmienione na `renew: "N"` z początkowym statusem „Prolongowano” i powodem
    „Osiągnięto limit prolongat”, żeby były dwa różne powody (REQ-L2). Odnawialne zostają `loan-001` i
    przeterminowane `loan-002`.
  - Prolongata wypożyczenia z `renew: "N"` jest teraz no-opem `200`, a wcześniej przesuwała termin. W
    prawdziwym Primo takie wypożyczenie się nie przedłuża, a klienci i tak nie wysyłają dla niego
    `renew_loans`.
  - `loanstatus` „Prolongowano” wynika z `_renewal_extensions` (albo `renewed_before` w szablonie), bez
    nowego stanu. `reset_state()` dalej resetuje wszystko.
  - `BRANCH_ADDRESS` i `location_code()` przeniesione z `search_data.py` do `data.py` (import w drugą stronę
    byłby cykliczny). Adres, kody lokalizacji i rok wypożyczenia są spójne z holdingiem i `creationdate`
    rekordu w katalogu.
  - Identyfikatory (`itemid`, `nzmmsid`, kody instytucji) celowo mockowe, bez kopiowania przykładowych
    numerów ze zlecenia.
  - Historia: 4 pozycje z fikcyjnych dzieł katalogu (`MOCK-SEARCH-A1/A2/B1/C1`), więc rekord istnieje.
  - Odnawialne wypożyczenia mają `renewstatuses: {"renewstatus": []}`. Tego kształtu nie widzieliśmy na
    żywo; zlecenie mówi tylko o nieodnawialnych.
- `run_all.sh`: check prolongaty (REQ-13 / REQ-L5) akceptuje termin bez zmian, jeśli kolejne +14 dni
  przekroczyłoby `maxrenewdate` (żywy Render trzyma stan między uruchomieniami). Nowa sekcja REQ-L1..L4 (3
  checki) i skrypt `20_loan_history.sh`.
- Testy: `pytest` 48/48 (nowy `tests/test_loan_details.py`, w tym `omnis-py` `get_loans("history")`),
  `ruff`/`black` czyste. `run_all.sh` lokalnie uruchomiony 3 razy pod rząd na tej samej instancji: 35/35
  za każdym razem, a trzeci przebieg przeszedł gałęzią „na limicie”.

## Faza 6 — zamówienia (REQ-H1..REQ-H12)

SPEC był w większości jednoznaczny. Co zrobione:

- `data.py`: stan zamówień modułowy z leniwą inicjalizacją (seed bierze tytuł z katalogu przez import lokalny,
  bo `search_data` importuje `data`). Wstrzykiwalny zegar `set_clock()`, `reset_state()` czyści też zamówienia,
  licznik `requestid` i zegar. `Requests` w `counters` liczone ze stanu.
- `search_data.py`: egzemplarze generowane deterministycznie (`MOCK-ITEM-<mmsid>-<n>`, `MOCKBC####`), jeden na
  edycję, plus drugi egzemplarz A1 w czytelni z `allowed: "N"`. Filia Demo 1 ma dwa miejsca odbioru
  (`MOCKLIB-FD1`, `MOCKLIB-FD1C`). `holding_status()` zastąpione przez `holding_items()` (nadal tylko z
  `holKey`, REQ-18b).
- `main.py`: trasy 12-15. Zdjęto ograniczenie REQ-18 „tylko niedostępne”: `getPhysicalService` odpowiada dla
  każdej edycji (REQ-H8).

Decyzje i odstępstwa:

- Limit 5 (REQ-H2) obejmuje seed: po złożeniu zamówienia przy 6 aktywnych wypada najstarsze złożone przez
  użytkownika, więc przy żywym seedzie użytkownik ma miejsce na 4. SPEC mówi o „5 aktywnych”, a `Requests` liczy
  seed, więc przyjąłem spójnie. Alternatywa (5 użytkownika + seed) to jedna stała w `MAX_ACTIVE_HOLDS`.
- `tests/test_guest_search.py::test_ils_holdings_works_without_authorization_header` sprawdzał
  `items == [{"itemstatusname": ...}]`, co przeczy REQ-H9 (pełny element). Poluzowałem asercję do
  `len(items) == 1` + `items[0]["itemstatusname"]`. To nie jest `test_contract.py`, ale to zmiana testu QA, do
  sprawdzenia.
- `cancel_requests` dla nieznanego id albo `request_type` ≠ `"holds"`: 200 z tą samą kopertą sukcesu i PUSTĄ
  listą `holds.hold`, bez zmiany stanu (SPEC mówi tylko „200 no-op”). Dzięki temu `omnis-py` nie rzuca.
- `itemQueue`: wymaga tokena z logowania (spójnie z `itemServices`, gość/brak -> 401), nieznany `itemId` -> 404.
- `GET` formularza i `POST` dla egzemplarza `allowed: "N"` -> 400 (SPEC nie precyzuje). `POST` waliduje też
  `requestType == "hold"`; `pickupLibraryId`, jeśli jest, musi równać się `pickupLocation`. `materialType` i
  `group_id` są ignorowane.
- REQ-H7: samo MMS id (z prefiksem `alma` lub bez) dopasowywane jest jako CAŁE wyrażenie do znanego mmsid, więc
  zwraca dokładnie jedną edycję (nie reprezentanta dzieła), a `A1` nie łapie `A10`. Inne zapytania działają jak
  dotąd.
- Seed: `MOCK-REQ-0001`, edycja `MOCK-SEARCH-B1`, odbiór Filia Demo 3. Jego `requestdate` i data „na półce do”
  liczone względem zegaru na bieżąco (nie starzeje się). Zamówienia użytkownika: `requestdate` z czasu złożenia.
- Mock dodaje zamówienie od razu (bez opóźnienia z prawdziwego Primo).

Testy: nowy `tests/test_holds_contract.py` (stan resetowany autouse). Testy pełnego przepływu przez
`get_holdable_items`/`place_hold` są pomijane (`hasattr(OmnisClient, "place_hold")`) na `omnis-py` z PyPI.
Uruchomienie przepływu lokalnie:

```bash
.venv/bin/pip install -e ../omnis-py     # tymczasowo, bez zmiany pyproject.toml
.venv/bin/python -m pytest -q            # 68 passed
.venv/bin/pip install "omnis-py==0.2.11" # powrót do stanu wyjściowego
.venv/bin/python -m pytest -q            # 66 passed, 2 skipped
```

`scripts/curl/21_holds.sh` i sekcja REQ-H w `run_all.sh` (48/48 lokalnie, dwa przebiegi pod rząd) mutują stan:
składają i anulują jedno zamówienie.
