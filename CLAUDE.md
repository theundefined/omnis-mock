# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Co to jest

Mock serwera Ex Libris Primo/OMNIS API (pełny kontrakt: `docs/SPEC.md`) — jedno stałe konto demo, fałszywe
wypożyczenia, zero połączenia z prawdziwą biblioteką. Powstał, bo `omnis-mobile` wymaga w Google Play danych
logowania do testów, a nikt w tym ekosystemie nie administruje siecią OMNIS — zamiast podawać czyjeś
prawdziwe dane, wystawiamy publiczny mock pod https://omnis-mock.onrender.com (własna domena była
rozważana, ale świadomie odrzucona — brak realnej korzyści, patrz `docs/DEPLOY_NOTES.md`).

Część większego ekosystemu opisanego w `../CLAUDE.md` (workspace `bracz`) — `omnis-py` jest źródłem prawdy
o kształcie prawdziwego API; ten projekt go odzwierciedla po stronie serwera, niezależnie od niego (nie
zależy od `omnis-py` w runtime, tylko jako dev-dependency do testu kontraktowego — patrz niżej).

## Ten projekt jest zaprojektowany pod pracę z subagentami — przeczytaj to przed czymkolwiek innym

`docs/PLAN.md` to fazowy plan z trzema rolami, zdefiniowanymi jako custom subagenty w `.claude/agents/`:
`developer`, `qa`, `devops`. Jeśli orkiestrujesz pracę nad tym repo:

1. Przeczytaj `docs/SPEC.md` (kontrakt — CO) i `docs/PLAN.md` (fazy, kryteria wyjścia — JAK/KIEDY) zanim
   zaczniesz cokolwiek zmieniać.
2. Uruchamiaj role przez `Agent` tool z `subagent_type` odpowiadającym nazwie pliku w `.claude/agents/`, w
   kolejności faz z `PLAN.md`. Nie pomijaj Fazy 2 (QA) nawet jeśli developer twierdzi, że skończył i testy
   są zielone — `docs/SPEC.md` wprost tłumaczy, dlaczego zielony `pytest` to nie to samo co zgodność ze
   specyfikacją.
   **Uwaga (sprawdzone empirycznie):** `subagent_type: "qa"`/`"developer"`/`"devops"` NIE działa, jeśli
   katalog roboczy sesji to `bracz/` (workspace nadrzędny), a nie `omnis-mock/` — harness nie skanuje
   zagnieżdżonych `.claude/agents/`. W takiej sytuacji użyj `subagent_type: "general-purpose"` i wklej
   całą treść odpowiedniego pliku z `.claude/agents/` wprost do prompta (tak jak to zrobiono w Fazie 2) —
   to jedyny sposób, żeby zachować ograniczenia roli (np. brak `Write`/`Edit` dla QA), skoro sam agent
   ogólnego przeznaczenia ma pełny dostęp do narzędzi.
3. `qa` celowo nie ma dostępu do `Write`/`Edit`. Jeśli subagent w tej roli zaczyna edytować kod zamiast
   raportować do `docs/QA_REPORT.md`, to sygnał, że coś jest nie tak z rolą/promptem, nie że "QA jest
   szybszy, jak może naprawiać na bieżąco".
4. Faza 4 (`devops`, wdrożenie na Render) ma twardy warunek wejścia: PASS w `docs/QA_REPORT.md`. Nie
   deployuj bez tego, nawet jeśli kod "wygląda gotowo".

## Komendy

```bash
pip install -e ".[dev]"
pytest -v                              # patrz uwaga niżej — to NIE są zwykłe testy jednostkowe
ruff check src
black --check src
uvicorn omnis_mock.main:app --reload   # lokalny serwer, http://localhost:8000

# Ręczne testowanie API bez pytest (przydatne przeciwko żywemu deployowi na Render, gdzie pytest
# się nie odpala) — patrz scripts/curl/README.md:
BASE_URL=https://omnis-mock.onrender.com scripts/curl/run_all.sh

# Izolowany venv z prawdziwym omnis-py z PyPI, skonfigurowanym pod tego mocka (NIE dotyka
# prawdziwego ~/.config/omnis-py/config.yaml użytkownika):
./scripts/setup_demo_client.sh [BASE_URL]
./demo-client/bin/omnis-cli-demo --renew
```

**`tests/test_contract.py` nie mockuje `omnis.client` — instaluje i uruchamia prawdziwy `OmnisClient` z PyPI
(`omnis-py`, dev-dependency w `pyproject.toml`) przeciwko lokalnie odpalonej instancji FastAPI, przez
`httpx.ASGITransport` (bez prawdziwego portu sieciowego).** To świadoma decyzja architektoniczna: jeśli
prawdziwe modele Pydantic klienta parsują odpowiedź mocka bez `ValidationError`, kontrakt trzyma się
silniej niż jakiekolwiek ręcznie pisane assercje. Ten plik jest kontraktem QA (patrz `.claude/agents/qa.md`)
— rola `developer` doprowadza go do zielonego stanu, ale go nie edytuje.

## Architektura

```
src/omnis_mock/
  main.py         FastAPI — routing; dokładny kształt JSON per endpoint w docs/SPEC.md (REQ-1..REQ-18b)
  auth.py         fake JWT (3 segmenty, payload ASCII-only — REQ-4) + rejestr ważnych tokenów (in-memory)
  data.py         fixture wypożyczeń demo-konta + stan po renew_loan (in-memory, resetowany co proces)
  search_data.py  fixture katalogu (3 fikcyjne dzieła) dla wyszukiwarki — bezstanowy, bez odpowiednika renew_loan
```

Celowo brak bazy danych — to jednorazowy, bezstanowy między restartami mock, nie produkcyjny system.
Layer 1 (login/counters/loans/renew_loans, REQ-1..REQ-13b) i Layer 2 (wyszukiwarka katalogu —
`pnxs`/`delivery`/`getPhysicalService`/`ILSServices/holdings`, REQ-14..REQ-18b, Faza 3 z `docs/PLAN.md`)
są w pełni zaimplementowane. Layer 1 zweryfikowany niezależnie przez QA (`docs/QA_REPORT.md`: PASS) oraz
wdrożony (`docs/DEPLOY_NOTES.md`); Layer 2 zweryfikowany `tests/test_search_contract.py` (analogiczny
oracle do Layer 1 — prawdziwy `OmnisClient`). Pełna lista pól JSON per endpoint Layer 2 i uzasadnienie
które pole jest zwracane przez realne Primo i kto (`omnis-py`/`omnis-mobile`) je faktycznie konsumuje:
`docs/API_FIELDS.md`.

`scripts/curl/` i `scripts/setup_demo_client.sh` — narzędzia do ręcznego eksplorowania API (patrz sekcja
Komendy wyżej i `scripts/curl/README.md`); `demo-client/` (generowane przez ten drugi skrypt) jest
gitignored, nigdy nie commitować.

## Nieoczywiste pułapki (pełne wyjaśnienie: docs/SPEC.md)

- `Loan` w `omnis-py` ma dokładnie 10 wymaganych kluczy — brak jednego to `ValidationError` u KAŻDEGO
  klienta w ekosystemie (`omnis-py`, `omnis-android`), nie tylko w tym mocku.
- `myaccount/counters` i `myaccount/fines` (drugi poza zakresem Layer 1) używają DWÓCH RÓŻNYCH formatów
  kwoty (`"0.00"` vs `"0,20 PLN"`) — ten sam serwer, dwa formaty. Mylenie ich to najłatwiejszy sposób, żeby
  implementacja wyglądała poprawnie, a i tak wywaliła klienta.
- `get_loans()` w `omnis-py` paginuje w pętli `while` dopóki `showmore` zawiera `"Y"` — fixture z
  `showmore: ["Y"]` i < 50 rekordów zawiesza klienta w NIESKOŃCZONEJ pętli HTTP, nie zwraca błędu. Jedyna
  pułapka w tym API, która realnie "wiesza" aplikację kliencką zamiast tylko zwracać złe dane.
- `holding.holKey` (obiekt z `POST /primaws/rest/pub/delivery`) jest **funkcjonalnie wymagany** przez
  realny `POST ILSServices/holdings/{id}` — bez niego endpoint zwraca `200 OK` z pustą listą `items`
  (brak terminu zwrotu) zamiast błędu, więc test, który sprawdza tylko `status_code`, nic tu nie dowodzi.
  Zweryfikowane empirycznie bisekcją pole-po-polu (`omnis-mobile/docs/api-verification-response.md`) —
  jedyne "dekoracyjne" pole `holding` spośród ~16 pozostałych, które ma realny wpływ na zachowanie API.
  `omnis-py` przekazuje cały `holding` 1:1 z powrotem w kolejnym żądaniu, więc mock musi wygenerować
  `holKey` w REQ-17, żeby REQ-18b w ogóle mogło zadziałać (SPEC.md, `docs/API_FIELDS.md`).
- `omnis-mobile` ma w pełni podpiętą pod UI wyszukiwarkę katalogu (`SearchScreen`) — od Fazy 3 `/pnxs`
  zwraca realne (fikcyjne) wyniki dla trafiających zapytań, `{"docs": []}` tylko gdy nic nie pasuje
  (REQ-14). Uwaga: `omnis-mobile`'s `data class Holding` (Kotlin) dziś **nie ma pola `holKey`** — dopóki
  to nie zostanie dodane po stronie `omnis-mobile` (rekomendacja w
  `omnis-mobile/docs/api-verification-response.md`, nie ruszona przez ten mock), termin zwrotu w apce
  mobilnej się nie rozwiąże, mimo że działa poprawnie dla `omnis-py`.
- Render (darmowy tier) usypia po bezczynności — sprawdź timeouty klienta PRZED poleganiem na tym jako
  koncie testowym dla Google Play (`docs/PLAN.md`, Faza 4) — inaczej mock istnieje, ale recenzent i tak
  dostanie błąd logowania przy pierwszej próbie.
- Test kontraktowy w Pythonie (`tests/test_contract.py`) NIE dowodzi, że Kotlinowy klient (`omnis-mobile`)
  też sparsuje odpowiedź poprawnie — inne (non-null) typy, inna serializacja. Weryfikacja Kotlina jest
  ręczna (`docs/PLAN.md`, Faza 5) i nie jest pokryta żadnym automatycznym testem w tym repo.
