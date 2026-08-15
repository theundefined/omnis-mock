# PLAN.md — plan realizacji `omnis-mock`

`docs/SPEC.md` mówi CO zbudować. Ten dokument mówi W JAKIEJ KOLEJNOŚCI, KTO (jaka rola/subagent) i JAK
poznać, że dana faza jest skończona. Fazy się nie przeskakuje — w szczególności Faza 2 (QA) nie jest
opcjonalna, nawet jeśli `pytest` jest zielony (patrz uzasadnienie w SPEC.md, sekcja "Kryterium akceptacji").

## Role (custom subagenty w `.claude/agents/`)

| Rola | Plik | Narzędzia | Czego NIE robi |
|---|---|---|---|
| `developer` | `.claude/agents/developer.md` | Read, Write, Edit, Bash, Glob, Grep | Nie edytuje `tests/test_contract.py`, nie deployuje |
| `qa` | `.claude/agents/qa.md` | Read, Bash, Glob, Grep | **Brak Write/Edit — celowo.** Jeśli coś jest nie tak, raportuje, nie naprawia |
| `devops` | `.claude/agents/devops.md` | Read, Write, Bash, Glob, Grep | Nie zaczyna bez PASS w `docs/QA_REPORT.md`, nie zmienia kodu klientów (`omnis-mobile` itd.) bez pytania |

Orkiestrujesz je przez `Agent` tool z `subagent_type` = nazwa roli, w kolejności faz poniżej. Każda faza ma
jasne kryterium wyjścia — nie przechodź dalej, dopóki nie jest spełnione.

## Faza 0 — Szkielet (zrobione)

Struktura katalogów, `docs/SPEC.md`, ten plik, puste moduły z sygnaturami, `Dockerfile`, `render.yaml`,
definicje subagentów, `tests/test_contract.py` (celowo czerwony). `git init` wykonany, **pierwszy commit
wymaga zgody użytkownika** (patrz Faza 0b).

### Faza 0b — pierwszy commit (człowiek, nie subagent)

Po zaakceptowaniu szkieletu: `git status` / `git diff --cached`, pokazać dokładny zakres użytkownikowi,
dopiero potem `git commit`. Zgodnie z globalną zasadą weryfikacji przed commitem — nie robić tego "w dobrej
wierze" w tle.

## Faza 1 — `developer`: implementacja Layer 1

**Wejście:** `docs/SPEC.md`, stuby w `src/omnis_mock/`, czerwone `tests/test_contract.py`.

**Zadania:**
1. `src/omnis_mock/data.py` — fixture demo-konta wg SPEC.md "Dane demo" (4 wypożyczenia, zróżnicowane stany,
   daty względem `date.today()`, stan renew w pamięci procesu, `reset_state()` dla testów).
2. `src/omnis_mock/auth.py` — `issue_token()` (fake JWT, payload ASCII-only — REQ-4), rejestr ważnych
   tokenów, `is_valid_token()`.
3. `src/omnis_mock/main.py` — podłączyć routing pod `data.py`/`auth.py` wg REQ-1 do REQ-14 w SPEC.md.
4. Odpalić `pytest -v` lokalnie i doprowadzić do zielonego stanu — **bez edytowania testu**. Jeśli test
   wydaje się błędny względem SPEC.md, to sygnał do zatrzymania się i zgłoszenia niezgodności, nie do
   samodzielnej zmiany testu.

**Wyjście:** zielony `pytest`, zielony `ruff check src` / `black --check src`, `docs/DEV_NOTES.md`
wypełniony (decyzje niejednoznaczne w SPEC.md, jeśli były jakieś — kilka zdań, nie esej).

## Faza 2 — `qa`: weryfikacja Layer 1

**Wejście:** kod z Fazy 1, `docs/DEV_NOTES.md`.

**Zadania:**
1. Niezależne uruchomienie `pytest -v`.
2. Przejście `docs/SPEC.md` REQ po REQ (REQ-1 … REQ-14) — zwłaszcza te oznaczone "(pułapka)": REQ-4 (JWT
   ASCII), REQ-7 (format kwoty w `counters`), REQ-10 (10 wymaganych pól loan), REQ-11 (paginacja/nieskończona
   pętla), REQ-14 (`/pnxs` bezpiecznik).
3. Ręczne testy edge case'ów przez `curl`/Bash, nieukryte w `tests/test_contract.py`: złe hasło → status
   kodu (musi być dokładnie 401), nieznany `loan_id` w `renew_loans` (musi być 200 no-op, nie 404/500), brak
   nagłówka `Authorization` na endpointach prywatnych.
4. Wypełnienie `docs/QA_REPORT.md` — PASS/FAIL per REQ, z konkretnym request/response dla każdego FAIL.

**Zasada:** zielony `pytest` to podłoga, nie sufit — możliwe jest PASS na testach i FAIL na jakimś REQ, który
test nie pokrywa dosłownie (np. dokładny kod błędu przy nieznanym `loan_id`).

**Wyjście:** `docs/QA_REPORT.md` z jednoznacznym werdyktem. FAIL → wraca do developera z konkretną listą.
PASS → można przejść do Fazy 4 (deploy) albo Fazy 3 (stretch), wg decyzji użytkownika.

## Faza 3 — `developer` + `qa`: Layer 2 (opcjonalna, stretch)

Pełny mock wyszukiwarki katalogu: `/primaws/rest/pub/pnxs` (realne wyniki zamiast `{"docs": []}`),
`/primaws/rest/pub/delivery`, `/primaws/rest/pub/getPhysicalService/{id}`,
`/primaws/rest/priv/ILSServices/holdings/{id}`, z 2-3 fikcyjnymi tytułami. Analogiczny cykl: developer
implementuje → aktualizuje `docs/SPEC.md` o nowe REQ-y → qa weryfikuje wg tego samego wzorca co Faza 2.

Nie zaczynaj tej fazy przed PASS w Fazie 2 — Layer 1 to jedyna rzecz wymagana do recenzji Google Play.

## Faza 4 — `devops`: wdrożenie na Render

**Status: wykonane.** Wynik w `docs/DEPLOY_NOTES.md` — publiczny URL: https://omnis-mock.onrender.com.
Własna domena (`unofficial-omnis.aramin.net`) była rozważana, ale świadomie odrzucona: bez realnej korzyści
funkcjonalnej (rozróżnienie "nieoficjalne" i tak jest w nazwie tenanta widocznej w apce, nie w domenie),
jedyna faktyczna zaleta (przenośność między dostawcami hostingu) nie była warta dodatkowego kroku na tym
etapie. Poniższe zadania zostają jako opis fazy na wypadek ponownego wdrożenia (np. po zmianie dostawcy).

**Warunek wejścia:** `docs/QA_REPORT.md` = PASS.

**Zadania:**
1. Dostosować `render.yaml`/`Dockerfile` do aktualnego stanu `pyproject.toml`.
2. Wdrożyć na Render (konto/repo GitHub — jeśli devops nie ma dostępu, przygotować dokładną instrukcję
   krok-po-kroku dla użytkownika zamiast zgadywać poświadczenia).
3. Zmienne środowiskowe (`DEMO_USERNAME`/`DEMO_PASSWORD`) w Render, health check `/healthz`.
4. **Zmierzyć cold start** po uśpieniu (Render free tier usypia po ~15 min bezczynności) i porównać z
   timeoutami klienta w `omnis-mobile` (`OmnisRepository.createClient`, OkHttp connect/read timeout). Jeśli
   timeout klienta < realny cold start → to ryzykuje cały cel projektu (recenzent Google Play dostanie błąd
   logowania). NIE zmieniać kodu klienta samodzielnie — opisać ryzyko i opcje (podniesienie timeoutu w
   apce / "obudzenie" serwisu przed wysłaniem do review / info w polu instrukcji testowych Google Play) w
   `docs/DEPLOY_NOTES.md` i zapytać użytkownika.
5. Smoke test na żywym URL-u — ten sam scenariusz co `tests/test_contract.py`, ale przeciwko publicznemu
   adresowi (nie commitować tymczasowej zmiany `base_url`).

**Wyjście:** `docs/DEPLOY_NOTES.md` — publiczny URL, wynik smoke testu, zmierzony cold start, rekomendacja
dot. timeoutów klienta.

**Bezpieczeństwo:** pierwszy `git push` / podłączenie repo do Render to akcja z realnym blast radius (publiczny
URL) — potwierdzić z użytkownikiem przed wykonaniem, nie zakładać zgody z wcześniejszej rozmowy.

## Faza 5 — integracja ręczna (człowiek + emulator, NIE subagent)

Dodanie mocka jako tymczasowego wpisu w `omnis-mobile`'s `Tenants.kt` (albo przez istniejącą opcję "Custom"
w UI), build, logowanie na emulatorze/urządzeniu, sprawdzenie czy ekran wypożyczeń i prolongata faktycznie
działają w apce. **To nie jest pokryte przez `tests/test_contract.py`** — Kotlin ma inne typy (non-null) i
inną serializację niż Pydantic, więc przejście testu kontraktowego w Pythonie nie dowodzi, że Kotlinowy
klient sparsuje tę samą odpowiedź bez wyjątku. Nazywamy tę lukę wprost, żeby nikt nie założył, że Faza 2
ją pokrywa.

## Kolejność w skrócie

```
Faza 0 (zrobione) → Faza 0b (commit, człowiek)
  → Faza 1 (developer) → Faza 2 (qa) ──PASS──→ Faza 4 (devops) → Faza 5 (człowiek, emulator)
                                    └─FAIL─→ wraca do Fazy 1
  (opcjonalnie, równolegle do/po Fazie 2 PASS: Faza 3 developer+qa dla Layer 2)
```
