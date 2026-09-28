# SPEC.md — kontrakt API `omnis-mock`

Ten dokument jest **jedynym źródłem prawdy** o tym, co `omnis-mock` musi zwracać. Kod (`src/omnis_mock/`),
testy (`tests/test_contract.py`, `tests/test_search_contract.py`) i raport QA (`docs/QA_REPORT.md`)
odwołują się do numerów wymagań (`REQ-*`) zdefiniowanych tutaj. Jeśli implementacja i ten plik się rozjadą
— SPEC.md wygrywa, chyba że ktoś świadomie go zaktualizuje.

Pełna lista pól JSON per endpoint wyszukiwarki katalogu (REQ-14..REQ-18b), z uzasadnieniem które pole jest
zwracane przez realne Primo i kto (`omnis-py`/`omnis-mobile`) je faktycznie konsumuje: `docs/API_FIELDS.md`.

## Cel

Mock serwera Ex Libris Primo / OMNIS, wystarczający by prawdziwi klienci (`omnis-py`, `omnis-mobile`,
`omnis-android`, `omnis-ha`) mogły się zalogować na jedno stałe konto demo, zobaczyć wypożyczenia i je
prolongować — **bez** dostępu do jakiejkolwiek prawdziwej biblioteki. Dostępny pod
https://omnis-mock.onrender.com, m.in. jako konto testowe dla recenzenta Google Play (autor `omnis-mobile`
nie jest administratorem sieci OMNIS i nie może podać prawdziwych danych logowania).

## Zakres

Layer 1 (konto demo, login, wypożyczenia, prolongata — REQ-1..REQ-13b), Layer 2 (wyszukiwarka katalogu —
REQ-14..REQ-18b, `docs/PLAN.md` Faza 3) oraz anonimowe wyszukiwanie tokenem gościa i wyszukiwanie po
autorze (REQ-G1..REQ-G5), a także wyszukiwanie po serii i rekord `pnxs/L/alma{mmsid}` (REQ-G6) są
zaimplementowane i muszą działać. `/fines`, `/requests` i pokrewne pozostają poza zakresem — patrz „Poza
zakresem” niżej.

### Konto demo

Dokładnie jedno konto, dane z env var (`DEMO_USERNAME`/`DEMO_PASSWORD`, patrz `.env.example`), z sensownymi
wartościami domyślnymi w repo (`demo` / `demo1234`) — **to nie jest sekret**, konto nie chroni żadnych
prawdziwych danych, więc trzymanie domyślnych wartości w repo jest bezpieczne i celowe (łatwość testowania).

**REQ-1**: Każde inne combo login/hasło niż skonfigurowane demo-konto musi kończyć się `401` na
`POST /primaws/suprimaLogin` — nigdy 200, nigdy inny kod błędu. `omnis-py`'s `OmnisClient.login()`
specjalnie rozpoznaje status `401` i zamienia go na `ValueError("Invalid credentials (401)")`; każdy inny
kod błędu przechodzi przez `response.raise_for_status()` jako `httpx.HTTPStatusError` — więc kod błędu ma
znaczenie, to nie jest szczegół implementacyjny.

### Endpointy

#### 1. `GET /discovery/search?vid={view}`

Cookie-priming w prawdziwym Primo. Klient go woła i ignoruje treść odpowiedzi.

- **REQ-2**: zwraca `200`, bez wymogu autoryzacji, treść odpowiedzi dowolna (może być pusta).

#### 2. `POST /primaws/suprimaLogin?lang=pl`

Content-Type: `application/x-www-form-urlencoded`. Pola formularza: `authenticationProfile`, `username`,
`password`, `institution`, `view`, `targetUrl` (ostatnie trzy mock może zignorować — nie ma wielu tenantów).

- **REQ-3**: dane zgodne z demo-kontem → `200` z body `{"jwtData": "<token>"}`. `token` to zwykły string
  JSON (klient robi `.strip('"')` na wyniku — więc dodatkowe cudzysłowy w środku stringa nie zaszkodzą, ale
  nie są wymagane; nie dodawaj ich bez potrzeby).
- **REQ-4 (pułapka, x2)**: `token` musi mieć **dokładnie 3 segmenty** rozdzielone kropką: `header.payload.signature`.
  - `payload` to base64 zawierające **poprawny JSON** z co najmniej kluczami `displayName` (string) i
    `userName` (string). Padding (`=`) opcjonalny — `omnis-py` sam go dopełnia przed dekodowaniem.
  - **Pułapka #1 — MUSI to być STANDARDOWY alfabet base64 (`+`/`/`), NIE urlsafe (`-`/`_`)**, mimo że
    prawdziwe JWT-y zwyczajowo używają base64url. Powód: `omnis-py` dekoduje payload przez zwykłe
    `base64.b64decode(...)`, które przy domyślnym `validate=False` PO CICHU ODRZUCA znaki spoza
    standardowego alfabetu zamiast rzucić błąd — token zakodowany jako urlsafe base64 zostałby bezgłośnie
    okaleczony przed `json.loads()` (losowy `JSONDecodeError` albo, gorzej, błędne dane bez żadnego
    wyjątku), zamiast czytelnie się wywalić. To nie jest teoretyczne — złap to od razu, zanim ktoś spędzi
    godzinę na debugowaniu "losowego" błędu dekodowania.
  - **Pułapka #2 — `displayName` musi być czystym ASCII** (np. `"Demo User"`, NIE `"Użytkownik Demo"`).
    Powód: `omnis-py` dekoduje payload przez `base64.b64decode(...).decode("utf-8")`, a Kotlinowy klient w
    `omnis-mobile` robi to przez `android.util.Base64` z innymi flagami — oba muszą dać identyczny wynik
    bajtowy, a polskie znaki diakrytyczne to najłatwiejszy sposób, żeby te dwie implementacje się rozjechały.
  - `header` i `signature` — treść dowolna, żaden klient jej nie weryfikuje (`omnis-py` w ogóle nie sprawdza
    podpisu).
- **REQ-1**: patrz wyżej — złe dane logowania → `401`.

#### 3. `GET /primaws/rest/priv/myaccount/counters?lang=pl`

Nagłówek: `Authorization: Bearer <token>`.

- **REQ-5**: bez ważnego tokena → `401`.
- **REQ-6**: z ważnym tokenem → `200`:
  ```json
  {
    "data": {
      "listofactions": {
        "action": [
          {"type": "Loans", "value": "4"},
          {"type": "Requests", "value": "0"},
          {"type": "Fines", "value": "0.00"}
        ]
      }
    }
  }
  ```
- **REQ-7 (pułapka — format kwoty #1)**: `Fines.value` MUSI być w formacie z kropką dziesiętną,
  `"0.00"` — `omnis-py` robi na tym polu bezpośrednio `float(fines_str)`. Przecinek (`"0,00"`) wywali
  `ValueError` po stronie klienta. **To jest INNY format niż w `/fines` (REQ-14 niżej) — ta sama usługa,
  dwa różne formaty kwoty na dwóch różnych endpointach, to zamierzona cecha prawdziwego Primo, nie błąd.**
  Wartość liczbowa powinna być spójna z sumą kar w fixture (patrz "Dane demo").

#### 4. `GET /primaws/rest/priv/myaccount/loans?bulk=&lang=pl&offset=&type=active`

Nagłówek: `Authorization: Bearer <token>`.

- **REQ-8**: bez ważnego tokena → `401`.
- **REQ-9**: kształt odpowiedzi:
  ```json
  {
    "data": {
      "loans": {
        "loan": [ /* obiekty loan, patrz REQ-10 */ ],
        "showmore": []
      }
    }
  }
  ```
- **REQ-10 (pułapka — kompletność pól)**: każdy obiekt `loan` MUSI zawierać **dokładnie te klucze jako
  wymagane** (`omnis-py`'s `Loan` model rzuci `ValidationError` przy braku któregokolwiek):
  `loanid`, `mmsid`, `title`, `duedate`, `duehour`, `loandate`, `loanstatus`, `ilsinstitutionname`,
  `mainlocationname`, `itembarcode` — wszystkie jako string. Opcjonalne (mogą być `null`/pominięte):
  `author`, `secondarylocationname`. Dodatkowo pole `renew` (`"Y"` lub `"N"`, string) — klient czyta je do
  wyliczenia `renewable`, nie jest częścią zadeklarowanego modelu, ale musi być obecne w surowym JSON-ie.
  Daty (`duedate`, `loandate`) w formacie `YYYYMMDD`.
- **REQ-11 (pułapka — nieskończona pętla)**: `showmore` musi być pustą listą (`[]`) albo nie zawierać
  `"Y"`, dopóki fixture ma mniej niż 50 wypożyczeń. `omnis-py`'s `get_loans()` robi `while True` i przerywa
  pętlę dopiero gdy `"Y" not in showmore` — fixture z `showmore: ["Y"]` przy małym zbiorze danych **zawiesza
  klienta w nieskończonej pętli HTTP**, nie zwraca błędu. To jedyny sposób, żeby ten mock realnie "zawiesił"
  aplikację kliencką, więc traktuj to jako wymóg krytyczny, nie stylistyczny.

#### 5. `POST /primaws/rest/priv/myaccount/renew_loans?lang=pl`

Nagłówek: `Authorization: Bearer <token>`, `Content-Type: application/json`. Body: `{"id": "<loanid>"}`.

- **REQ-12**: bez ważnego tokena → `401`.
- **REQ-13**: znany `id` → `200` z dowolnym JSON-em w body (klient nie waliduje kształtu odpowiedzi, tylko
  status), **i** stan w pamięci procesu musi się zmienić tak, by kolejne `GET .../loans` zwróciło **nowy,
  późniejszy `duedate`** dla tego loanu (np. `+14 dni` od aktualnego terminu). Bez tej mutacji cały sens
  demonstrowania prolongaty znika.
- **REQ-13b**: nieznany `id` → `200` (no-op, nie `404`) — celowa decyzja, żeby nie testować ścieżek błędów,
  których `omnis-py` i tak nie obsługuje specjalnie (każdy status ≠ 2xx poza `login`'s `401` leci przez
  `raise_for_status()` jako wyjątek).

#### 6. `GET /primaws/rest/pub/pnxs` — wyszukiwarka katalogu (Layer 2)

`omnis-mobile` ma **w pełni podpięty pod UI** ekran wyszukiwania katalogu (`SearchScreen`). Od Fazy 3
(`docs/PLAN.md`) ten endpoint zwraca realne (fikcyjne) wyniki dla zapytań trafiających w fixture
(`src/omnis_mock/search_data.py`) — pełna lista pól i uzasadnienie ich włączenia/wykluczenia względem
realnego Primo: `docs/API_FIELDS.md`.

- **REQ-14**: zapytanie **niczego nie trafiające** w fixture zwraca `200` z `{"docs": [], "info": {...}}`
  (dokładnie zachowanie sprzed Layer 2, patrz REQ-15 niżej dla dokładnego kształtu `info`). Bez tokena
  działa tak samo jak z tokenem.
- **REQ-15 (dopasowanie top-level)**: `q="any,contains,<query>"` (inne pola niż `any`, np. `creator`,
  opisuje REQ-G5) — mock wyciąga `<query>` i dopasowuje
  **case-insensitive substring całego zapytania** względem `"{tytuł} {autor}"` danego dzieła. Świadomie
  **NIE tokenizacja/OR** — jedno ogólne słowo w zapytaniu nie może trafić przypadkiem w żaden z fikcyjnych
  rekordów fixture, bo zepsułoby to REQ-14 (np. `search_books("cokolwiek")` musi zostać pusty). Wynik: **co
  najwyżej jeden `doc` na `frbrgroupid`** (real Primo grupuje wyniki tak samo), reprezentowany przez
  najnowszą edycję danego dzieła. Odpowiedź niesie też kopertę `info` (`total`, `totalResultsLocal`,
  `totalResultsPC`, `first`, `last`) honorującą `offset`/`limit` z query params — `omnis-mobile` czyta
  `info.total` do paginacji "Załaduj więcej" (`omnis-py` tego pola nie czyta, ale musi być obecne).
- **REQ-16 (group expansion)**: `qInclude="facet_frbrgroupid,exact,<id>"` zwraca **wszystkie** edycje
  dzieła o danym `frbrgroupid`, posortowane malejąco po dacie (`sort=date_d`, jak realne Primo), bez
  paginacji przez `offset`/`limit` (tak jak w realnym API dla tego trybu).

#### 7. `POST /primaws/rest/pub/delivery` — dostępność per filia (Layer 2)

Body: goła lista stringów JSON (alma-id, prefiks `alma`), **nie** model — klient wysyła `json=<lista>`
bezpośrednio.

- **REQ-17**: zwraca listę `{"pnx": {"control": {"recordid": [...]}}, "delivery": {"holding": [...]}}` po
  jednym elemencie na **znane** przekazane alma-id (nieznane pomijane, nie błąd). Każdy `holding` niesie
  **pełny, realistyczny zestaw pól** (nie tylko te czytane przez `omnis-py`) — patrz `docs/API_FIELDS.md`,
  sekcja `delivery.holding[]`, dla pełnej listy i uzasadnienia. Mock **nie** waliduje, że `q`/`qInclude` w
  query params odpowiadają grupie przekazanych id (świadome uproszczenie, uzasadnienie:
  `docs/API_FIELDS.md`, "Świadome uproszczenia").

#### 8. `GET /primaws/rest/pub/getPhysicalService/{bare_mmsid}` (Layer 2)

- **REQ-18**: znany `bare_mmsid` (bez prefiksu `alma`) z niedostępną edycją w fixture → `200` z
  `{"physicalServiceId": "PS-<bare_mmsid>"}`. Nieznany `bare_mmsid` → `404` (klient łapie to jako
  `httpx.HTTPError` → `None`, oczekiwana ścieżka degradacji, `omnis-py/src/omnis/client.py:519-536`).

#### 9. `POST /primaws/rest/priv/ILSServices/holdings/{physicalServiceId}` (Layer 2)

Nagłówek `Authorization` jest **ignorowany** — mimo ścieżki `priv` endpoint działa bez tokena, z tokenem
gościa i z tokenem z logowania, tak jak prawdziwe Primo (REQ-G2 niżej). Do REQ-G2 wymagał tokena z
logowania.

- **REQ-18b (pułapka, analogiczna do REQ-4/REQ-7/REQ-10/REQ-11)**: odpowiedź niesie `itemstatusname`
  (`data.itemInfo.locations[].items[].itemstatusname`, string z datą `dd/mm/rrrr`, zawierający
  `"przekroczon"` gdy termin minął) **TYLKO gdy przychodzące body zawiera niepusty `holKey` w
  `locations[0]`** — w przeciwnym razie `200` z **pustą listą** `data.itemInfo.locations` (**nie** `404`).
  To replikuje empirycznie zweryfikowane zachowanie realnego Primo (`omnis-mobile/docs/api-verification-
  response.md`, ustalone bisekcją pole-po-polu): `holKey` jest jedynym z ~16 "dekoracyjnych" pól obiektu
  `holding`, które faktycznie wpływa na to, czy ten endpoint zwróci dane. Ponieważ `omnis-py` przekazuje
  cały `holding` (pobrany z REQ-17) 1:1 z powrotem w tym żądaniu, poprawne zachowanie tego REQ-u zależy od
  tego, że REQ-17 faktycznie wygenerował `holKey` — to jedyna rzecz w Layer 2, która realnie odróżnia
  "wierny mock" od mocka, który tylko wygląda podobnie na happy path.
  **Zachowanie zależy od tenanta** (sprawdzone na żywo 2026-09-28, `docs/DEV_NOTES.md`): Raczyńskich
  (`48OMNIS_BRP`) wymaga `holKey`, a Dolnośląska Biblioteka Publiczna (`48OMNIS_WBP`) zwraca termin
  zwrotu także bez niego. Mock celowo odwzorowuje surowszy wariant.

### Anonimowe wyszukiwanie (token gościa) i wyszukiwanie po autorze — REQ-G1..REQ-G5

Źródło: zlecenie `omnis-mobile/docs/omnis-mock-guest-search-spec.md` (2026-09-28). Wszystkie zachowania
opisane tam jako zweryfikowane na żywo na prawdziwym Primo (Biblioteka Raczyńskich + 53 inne tenanty).
`omnis-mobile` wyszukuje w katalogu **bez logowania**, tak jak oficjalny interfejs WWW Primo: pobiera token
gościa i nim wykonuje cały pipeline z endpointów 6–9. Aplikacja nie ma wyjątków dla trybu demo, więc mock
musi to obsłużyć tak jak prawdziwe Primo.

#### 10. `GET /primaws/rest/pub/institution/{institution}/guestJwt`

Wywołanie aplikacji: `?isGuest=true&lang=pl&targetUrl=<dowolny URL>&viewId=MOCK:MOCK`.

- **REQ-G1**: `200`, `Content-Type: application/json;charset=UTF-8` (dokładnie tak, z charsetem). Body to
  **literał stringu JSON** — token w cudzysłowach (`"eyJ...x.y"`), **nie** obiekt `{"jwtData": ...}` jak w
  `suprimaLogin`; klient zdejmuje cudzysłowy.
  - Token: 3 segmenty i kodowanie jak w REQ-4 (standardowy alfabet base64, bez paddingu, payload ASCII).
    Payload ma kluczowe pola prawdziwego tokena gościa: `iss: "Prima"`, `userName` = `user` =
    `"anonymous-<MMDD_HHMMSS>"`, `displayName: null`, `userGroup: "GUEST"`, `institution` (ze ścieżki),
    `viewId` (z query), `signedIn: null`, `onCampus: "false"`, `language` (z `lang`, domyślnie `"en"`),
    `iat`, `exp` (`iat + 24h`, mock nie sprawdza wygaśnięcia).
  - Każde wywołanie może wydać nowy token. Token jest zapisywany jako **token gościa**, w rejestrze
    oddzielnym od tokenów z logowania (`auth.token_kind()`: `"login"` / `"guest"` / `None`).
  - Brak `viewId` (np. `GET .../guestJwt` bez query) → `400` z pustym body. Inne parametry są opcjonalne.

- **REQ-G2**: cztery endpointy wyszukiwarki (`pnxs`, `delivery`, `getPhysicalService`,
  `ILSServices/holdings`) **nie sprawdzają `Authorization`**. Działają tak samo bez nagłówka, z tokenem
  gościa, z tokenem z logowania, a nawet z nieznanym tokenem. Dla pierwszych trzech tak było od początku
  (REQ-14). Realna zmiana dotyczy `priv/ILSServices/holdings` (sekcja 9), bo prawdziwe Primo też go nie
  zabezpiecza (sprawdzone na 8 tenantach). Pułapka `holKey` (REQ-18b) działa bez zmian.

- **REQ-G3 (pułapka, analogiczna do REQ-7/REQ-11)**: token gościa **nie** daje dostępu do konta.
  `GET myaccount/loans`, `GET myaccount/counters` i `POST myaccount/renew_loans` z tokenem gościa zwracają
  **`200`** (nie 401!) z dokładnie takim body:
  ```json
  {"beaconO22":"0","status":"failed","reply-code":"0002","reply-text":"The patron ID is invalid","data":null}
  ```
  Klient, który sprawdza tylko kod HTTP, uzna to za sukces. Zachowanie dla `renew_loans` przyjęto
  analogicznie, bo nie było testowane na żywo. Taki `renew_loans` **nie mutuje** stanu wypożyczeń. Brak
  tokena albo nieznany token → `401` jak dotąd (REQ-5/REQ-8/REQ-12).

- **REQ-G4** (`pnxs`, parametr `scope`): akceptowane są `MyInstitution` (nowe `omnis-mobile`),
  `MyInstitution2` (`omnis-py` i starsze `omnis-mobile`) oraz brak parametru lub pusta wartość. Każda inna
  wartość → `400` z **pustym** body, tak jak w prawdziwym Primo. `tab` jest ignorowany, tak jak w
  prawdziwym Primo. `scope` jest sprawdzany tylko w `pnxs`: `delivery` go nie waliduje, zgodnie z
  uproszczeniem z REQ-17.

- **REQ-G5** (`pnxs`, pole w `q`): `q` jest parsowane jako `<pole>,<operator>,<wartość>`, z podziałem
  **tylko na dwóch pierwszych przecinkach**, bo wartość może zawierać przecinki (`creator,contains,Weir,
  Andy`). Operator jest ignorowany i zawsze działa jak `contains`. `q` bez dwóch przecinków jest traktowane
  jako `any` z całym `q` jako wartością.
  - `any` (i każde nieznane pole) → dopasowanie jak w REQ-15: tytuł + autor.
  - `creator` → dopasowanie **wyłącznie do autora**, nie do tytułu. `creator,contains,Cienie` nic nie
    znajduje, choć `any,contains,Cienie` trafia.
  - Dopasowanie w obu trybach (także REQ-15): case-insensitive substring po normalizacji (przecinki
    zamienione na spacje, zwinięte białe znaki), względem autora w **obu** zapisach: naturalnym
    („Karolina Nibylska”) i odwróconym („Nibylska, Karolina”). Dzięki temu `"Nibylska, Karolina"`,
    `"Nibylska Karolina"` i `"Karolina Nibylska"` dają ten sam wynik, tak jak w prawdziwym Primo
    („Weir, Andy” i „Weir Andy” zwracają te same 3 wyniki).
  - `qInclude` (group expansion, REQ-16) dalej ignoruje `q`. Aplikacja przekazuje tam to samo
    `q=creator,...`, co nie ma wpływu na wynik.
  - Format autora w katalogu: patrz „Dane katalogu” niżej (`addata.au` = „Nazwisko, Imię”).

- **REQ-G6** (pole `series` w `q` + rekord). Zlecenie zostało rozszerzone 2026-09-28 dla `omnis-mobile`
  v0.6.1/v0.6.2.
  - `q=series,contains,<nazwa>` → case-insensitive substring (po tej samej normalizacji co REQ-G5)
    **wyłącznie** na całym `addata.seriestitle`, łącznie z tomem i odpowiedzialnością. Nie dopasowuje
    tytułu ani autora. Aplikacja wysyła nazwę serii obciętą od pierwszego `;` i od pierwszego ` / `:
    `"Dzieła wszystkie / Adam Mickiewicz ; [t. 4]"` → `Dzieła wszystkie`. Na prawdziwym Primo (BRACZ,
    2026-09-28) dopasowanie działa na słowach (`series,contains,Potter Harry` = 30, tak samo jak `Harry
    Potter`), a mock świadomie używa substringu, zgodnie ze zleceniem. Kliknięcie „Seria: …” wysyła
    niezmieniony fragment `seriestitle`, więc wynik jest ten sam. Różnica może się pojawić tylko przy
    tekście wpisanym ręcznie w trybie wyszukiwania po serii.
  - `series` nie wchodzi do dopasowania `any` (REQ-15 bez zmian).

#### 11. `GET /primaws/rest/pub/pnxs/L/{recordId}` — pełny rekord (REQ-G6)

`recordId` = `alma<mmsid>`, query `vid`, `lang`. Endpoint jest publiczny i nie sprawdza `Authorization`.

- **REQ-G6 (rekord)**: znany rekord → `200` z `{"pnx": <ten sam pnx co w wynikach wyszukiwania>,
  "delivery": {"holding": [<ten sam holding co w REQ-17, z holKey>]}}`.
  - `omnis-mobile` (v0.6.2) bierze stąd `addata.seriestitle` i `addata.au` wypożyczeń, bo API wypożyczeń
    serii nie podaje. Adres filii dobiera przez `delivery.holding[].mainLocation` == `mainlocationname`
    wypożyczenia.
  - `omnis-py` (`get_record_details`) czyta `pnx.display`/`addata.isbn`.
- Nieznany rekord → `200` z pustą kopertą wyszukiwania `{"info": {"total": 0, ...}, "facets": [], "docs":
  []}`, **bez `pnx`**. Tak odpowiada prawdziwe Primo, **nie** `404`. `omnis-mobile` zapisuje to jako
  „sprawdzone, bez serii” i nie ponawia zapytania.

## Endpointy pomocnicze (poza kontraktem Primo)

Nie są częścią API, którego oczekuje `OmnisClient`/`omnis-mobile` — nie testuje ich `tests/test_contract.py`
i żaden REQ-numer ich nie obejmuje. Istnieją wyłącznie dla człowieka trafiającego pod ten URL bezpośrednio
(np. recenzent Google Play sprawdzający, czy serwis żyje) albo dla botów/wyszukiwarek.

- **`GET /`** — strona statusu (HTML): wersja (`__version__`), commit (z `RENDER_GIT_COMMIT`, jeśli
  wdrożone na Render — lokalnie po prostu "dev"), uptime procesu, link do repo na GitHubie, link do
  `docs/SPEC.md`, i dane konta demo (login/hasło/**base_url**) — pokazane wprost, bo to jawnie nie-sekret
  (patrz "Dane demo" wyżej), a to ułatwia komuś wypróbowanie apki bez szukania w dokumentacji. Musi zawierać
  wyraźne zastrzeżenie "to nie jest prawdziwa biblioteka/OMNIS".
  - **`base_url` MUSI być wyliczony z requestu** (`_external_base_url()` w `main.py`: nagłówki
    `X-Forwarded-Proto`/`X-Forwarded-Host`, z fallbackiem na `request.url`), **NIE hardkodowany** jako
    konkretna domena (Render czy jakakolwiek inna) — ten sam kod ma pokazywać poprawną wartość niezależnie
    od tego, pod jakim URL-em serwis akurat żyje (localhost, Render, ewentualna przyszła zmiana hostingu).
    To bezpośrednia konsekwencja decyzji o nietrzymaniu się jednej konkretnej domeny (patrz
    `docs/DEPLOY_NOTES.md`, sekcja "Własna domena").
- **`GET /robots.txt`** — `Disallow: /` dla wszystkich botów. Razem z meta-tagiem `noindex` na stronie
  statusu: to publiczny mock pod ogólnodostępnym URL-em, nie chcemy, żeby wyszukiwarki go zindeksowały i
  ktoś trafił tu myśląc, że to prawdziwa biblioteka.

## Poza zakresem (Layer 2 zaimplementowane, patrz REQ-14..REQ-18b wyżej; reszta poniżej wciąż nie)

- `GET /primaws/rest/pub/pnxs/L/alma{mmsid}` przeniesiony do zakresu w REQ-G6 (endpoint 11). Do tego czasu
  odpowiadał `404`.
- `/primaws/rest/priv/myaccount/fines` — osobny endpoint, **inny format kwoty**: string typu `"0,20 PLN"`
  (przecinek jako separator dziesiętny + sufiks waluty), parsowany przez `omnis-py`'s `_parse_fine_amount()`.
  To jest **REQ-format-kontrastowy** do REQ-7 wyżej — jeśli kiedyś implementujesz `/fines`, NIE używaj tam
  formatu z kropką.
- `/primaws/rest/priv/myaccount/requests`, `/primaws/rest/priv/myaccount/personal_settings`,
  `/primaws/rest/priv/myaccount/cancel_requests`.

## Dane demo (fixture)

- Jedno konto (`DEMO_USERNAME`/`DEMO_PASSWORD`).
- 4 wypożyczenia, tytuły z domeny publicznej (polska klasyka: np. "Pan Tadeusz", "Lalka", "Quo Vadis",
  "Dziady") — celowo, żeby uniknąć jakichkolwiek wątpliwości co do praw autorskich w publicznie dostępnym
  demo.
- Zróżnicowane stany (żeby demo faktycznie coś pokazywało w UI, nie samą zieloną listę):
  - **co najmniej jedno przeterminowane** (`duedate` w przeszłości),
  - **co najmniej jedno `renew: "Y"`** i **co najmniej jedno `renew: "N"`**,
  - reszta z różnymi, ale rozsądnymi terminami w przyszłości.
- **Daty liczone względem `date.today()` w momencie odpowiedzi, nie hardkodowane** — inaczej demo
  "zestarzeje się" (wszystko stanie się przeterminowane) tydzień po wdrożeniu. Trzymaj w kodzie *przesunięcia*
  (`timedelta` względem dziś), nie absolutne daty.
- Stan po `renew_loan` — w pamięci procesu (moduł-level, jedno konto = brak potrzeby na sesyjność per-user).
  Restart procesu resetuje wszystko do stanu początkowego. To jest zamierzone, nie luka.

### Dane katalogu (fixture wyszukiwarki, `src/omnis_mock/search_data.py`)

- 3 fikcyjne dzieła, jawnie zmyślone tytuły/autorzy (publiczny mock — nie przypisujemy fałszywej
  dostępności możliwej do zidentyfikowania osobie): „Cienie Nibylandii" (2 wydania — ćwiczy REQ-16 group
  expansion), „Ostatni Rejs Wyobraźni" (1 wydanie, w całości dostępne), „Biblioteka Za Mgłą" (1 wydanie,
  niedostępne).
- **Plus 4 dzieła wygenerowane z `data._LOAN_TEMPLATES`** (`_works_from_loans()` w `search_data.py`) — te
  same tytuły/`mmsid` co 4 wypożyczenia demo-konta z "Dane demo" wyżej, każde oznaczone
  `availability_status: "unavailable"` z `due_offset_days` **identycznym** jak termin zwrotu danego
  wypożyczenia. Bez tego wyszukiwarka i konto demo pokazywałyby dwa rozłączne zbiory książek — tytuł
  wypożyczony na koncie demo byłby niewyszukiwalny w katalogu.
- Zróżnicowane stany dostępności, jak w "Dane demo" dla wypożyczeń: co najmniej jedna niedostępna wersja z
  terminem **przeszłym** (przeterminowanym, `overdue=True`) i co najmniej jedna z terminem **przyszłym**
  (`overdue=False`) — obie gałęzie reguły "przekroczon" z REQ-18b muszą być pokryte.
- **Serie (REQ-G6)**: dwa wypożyczenia demo, „Pan Tadeusz” i „Dziady”, należą do serii „Dzieła wszystkie”
  z różnym zapisem tomu i odpowiedzialności: `"Dzieła wszystkie / Adam Mickiewicz ; [t. 4]"` i `"Dzieła
  wszystkie ;  3"`. Dzięki temu „Seria: …” przy wypożyczeniu w aplikacji prowadzi do obu tomów. „Cienie
  Nibylandii” ma serię `"Kroniki Nibylandii / Karolina Nibylska ; 1"`. Pozostałe dzieła są bez serii
  (`seriestitle: []`).
- **Format autora (REQ-G5)**: fixture trzyma autora w naturalnej kolejności („Karolina Nibylska”), tak jak
  `display.title` („Cienie Nibylandii / Karolina Nibylska.”) i wypożyczenia w `data.py`, które się nie
  zmieniają. Pola `addata.au`, `addata.addau`, `sort.author` i `display.contributor` mają format prawdziwego
  Primo, czyli „Nazwisko, Imię” („Nibylska, Karolina”, „Mickiewicz, Adam”). `aulast`/`aufirst` to
  odpowiednio nazwisko i imię. `omnis-py` bierze autora wyniku z `addata.au`, więc
  `SearchResult.author == "Nibylska, Karolina"`.
- Katalog jest **bezstanowy** (bez odpowiednika `_renewal_extensions`) — daty w `itemstatusname` liczone
  względem `date.today()` przy każdym żądaniu, tak samo jak wypożyczenia w "Dane demo" wyżej.
  `_works_from_loans()` czyta wyłącznie statyczny `data._LOAN_TEMPLATES`, nigdy `data.get_demo_loans()` ani
  `data.renew_demo_loan()`, więc prolongata wypożyczenia nie zmienia terminu widocznego w wyszukiwarce.

## Bezpieczeństwo / ograniczenia (obowiązują niezależnie od fazy)

- Zero prawdziwych danych osobowych.
- Zero wywołań do prawdziwego Primo, prawdziwego OpenLibrary, czy jakiegokolwiek innego zewnętrznego API z
  wnętrza mocka — to ma być całkowicie izolowany, samowystarczalny serwer.
- Tylko jedno, stałe, skonfigurowane konto — nie akceptuj dowolnych danych logowania jako "ważnych" (patrz
  REQ-1). To nie jest tylko poprawność kontraktu — publiczny serwer akceptujący dowolne dane logowania jako
  "zalogowany" to zaproszenie do nadużyć.

## Kryterium akceptacji — PRIMARY oracle

Główny test to **nie** ręcznie pisane assercje, tylko uruchomienie prawdziwego `OmnisClient` z opublikowanej
paczki `omnis-py` (PyPI) przeciwko temu mockowi (patrz `tests/test_contract.py`, już napisany i celowo
czerwony do czasu implementacji):

```python
client = OmnisClient(base_url="...", client=<httpx client wpięty w in-process FastAPI app>)
await client.login(DEMO_USERNAME, DEMO_PASSWORD, institution="MOCK", view="MOCK:MOCK")
info = await client.get_user_info()
loans = await client.get_loans()
await client.renew_loan(loans[0].id)
```

Jeśli to przechodzi bez `ValidationError` i bez nieobsłużonych wyjątków HTTP — kontrakt trzyma. To silniejszy
test niż cokolwiek napisanego ręcznie, bo korzysta z prawdziwych modeli Pydantic klienta, nie z założeń
autora mocka o tym, co klient akceptuje.

**Ten test NIE dowodzi, że Kotlinowy klient (`omnis-mobile`) też sparsuje odpowiedź poprawnie** — Kotlin ma
inne (non-null) typy i inną serializację. Weryfikacja Kotlina jest ręczna — patrz `docs/PLAN.md`, Faza 5.

Dla Layer 2 (REQ-14..REQ-18b) analogicznym oracle jest `tests/test_search_contract.py`: `client.search_books(...)`
przez prawdziwego `OmnisClient`, z asercjami na polach liściach (`edition`, `branches[].status`,
`branches[].due_date`, `branches[].overdue`), nie tylko na długości listy wyników — samo `len(results) > 0`
nic nie dowodzi, bo `omnis-py` łyka błędy HTTP z `getPhysicalService`/`ILSServices` po cichu (patrz
`docs/API_FIELDS.md`, uzasadnienie REQ-18b).

Dla REQ-G1..REQ-G6: `tests/test_guest_search.py`. Dla REQ-G6 test odtwarza ścieżkę aplikacji od
wypożyczenia przez rekord do `q=series`, z kopią `seriesSearchTerm` z `Models.kt`, i sprawdza też
prawdziwy `OmnisClient.get_record_details`. REQ-G2 sprawdza prawdziwy `OmnisClient` **bez
logowania**, z tokenem gościa: asercja na `due_date`, która dowodzi, że `ILSServices/holdings` przyjął
token gościa. Reszta to surowe `httpx`, bo `omnis-py` nie ma API do `guestJwt` ani `q=creator`, a
`get_loans()` wywróciłby się na `"data": null` z REQ-G3, zamiast pozwolić to sprawdzić.
