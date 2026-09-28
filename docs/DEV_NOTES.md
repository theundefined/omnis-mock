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
