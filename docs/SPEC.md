# SPEC.md — kontrakt API `omnis-mock`

Ten dokument jest **jedynym źródłem prawdy** o tym, co `omnis-mock` musi zwracać. Kod (`src/omnis_mock/`),
testy (`tests/test_contract.py`) i raport QA (`docs/QA_REPORT.md`) odwołują się do numerów wymagań (`REQ-*`)
zdefiniowanych tutaj. Jeśli implementacja i ten plik się rozjadą — SPEC.md wygrywa, chyba że ktoś świadomie
go zaktualizuje.

## Cel

Mock serwera Ex Libris Primo / OMNIS, wystarczający by prawdziwi klienci (`omnis-py`, `omnis-mobile`,
`omnis-android`, `omnis-ha`) mogły się zalogować na jedno stałe konto demo, zobaczyć wypożyczenia i je
prolongować — **bez** dostępu do jakiejkolwiek prawdziwej biblioteki. Docelowo dostępny pod
`unofficial-omnis.aramin.net`, m.in. jako konto testowe dla recenzenta Google Play (autor `omnis-mobile` nie
jest administratorem sieci OMNIS i nie może podać prawdziwych danych logowania).

## Zakres — Layer 1 (wymagane, ta faza)

Wszystko poniżej musi działać. Layer 2 (pełna wyszukiwarka katalogu) jest osobną, opcjonalną fazą — patrz
`docs/PLAN.md`.

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

#### 6. `GET /primaws/rest/pub/pnxs` (siatka bezpieczeństwa, nie pełny mock)

`omnis-mobile` ma **w pełni podpięty pod UI** ekran wyszukiwania katalogu (`SearchScreen`), mimo że pełny
mock wyszukiwarki to Layer 2 (poza zakresem tej fazy). Bez tego endpointu ekran wyszukiwania w apce pokaże
błąd, a nie pusty wynik.

- **REQ-14 (bezpiecznik)**: dla dowolnego zapytania (dowolne query params, z tokenem lub bez) zwraca `200`
  z `{"docs": []}`. To VS Layer 2, gdzie te same query params zwracałyby prawdziwe fikcyjne wyniki.

## Poza zakresem Layer 1 (Layer 2 / stretch — patrz `docs/PLAN.md`, Faza 3)

- Pełny mock `/primaws/rest/pub/pnxs` z realnymi wynikami + `/primaws/rest/pub/delivery` +
  `/primaws/rest/pub/getPhysicalService/{id}` + `/primaws/rest/priv/ILSServices/holdings/{id}`.
- `GET /primaws/rest/pub/pnxs/L/alma{mmsid}` (`get_record_details` w `omnis-py`) — osobny endpoint od
  wyszukiwarki, zwraca pełne metadane pojedynczej książki (okładka, ISBN, wydawca). Bez niego `omnis-cli
  --format json`/`--format csv` (które w odróżnieniu od domyślnego widoku tabelarycznego pobierają te
  detale) dostają `404` przy próbie wzbogacenia każdego loanu — ale `omnis-py`'s `fetch_account_data` łapie
  ten błąd per-konto i wpisuje go jako `"error"` w wyniku, więc to CZYSTA degradacja, nie crash i nie utrata
  reszty danych. Zweryfikowane empirycznie (Faza 1, test manualny z `omnis-cli`) — domyślny widok
  tabelaryczny (bez `--format json/csv`) i `omnis-mobile`'s `getLoansForAccount` w ogóle tego endpointu nie
  wołają, więc to nie blokuje głównego celu (recenzja Google Play).
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
