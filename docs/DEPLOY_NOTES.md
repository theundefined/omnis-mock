# DEPLOY_NOTES.md

Wypełnione podczas Fazy 4 (`docs/PLAN.md`), wykonanej przez tę samą sesję co Fazy 1-2 (nie przez osobnego
subagenta `devops`) — z asystą użytkownika w przeglądarce (logowanie/autoryzacja w Render było wykonane
przez użytkownika, nie przez agenta).

## Wdrożenie

- Publiczny URL (Render): **https://omnis-mock.onrender.com**
- Data wdrożenia: 2026-08-15
- Repo: `github.com/theundefined/omnis-mock` (public), branch `main`, deploy przez Render Blueprint
  (`render.yaml`), auto-deploy włączony (GitHub połączony przez OAuth).
- Zmienne środowiskowe ustawione przez `render.yaml` (`DEMO_USERNAME`/`DEMO_PASSWORD`) — nie-sekretne,
  patrz `docs/SPEC.md`.
- **Napotkany i naprawiony błąd `render.yaml`**: Render odrzucił oryginalny plik —
  `services[0].envVars[1] cannot simultaneously specify fields value and sync`. Pole `sync: false` nie może
  współistnieć z `value:` w tym samym `envVar`. Naprawione (usunięto `sync: false`, `DEMO_PASSWORD` zostaje
  jako zwykły `value`, skoro i tak nie jest sekretem) — commit `a0d7849`, przed czym Blueprint się nie dał
  w ogóle utworzyć.

## Smoke test na żywo

Ten sam scenariusz co `tests/test_contract.py`, uruchomiony ręcznie przez `curl` przeciwko publicznemu
URL-owi (nie automatyczny pytest — public URL nie jest częścią zautomatyzowanego test suite).

- **Wynik: PASS.** Pełny cykl login → counters → loans → renew_loans zweryfikowany: `POST
  /primaws/suprimaLogin` z demo-danymi → `200` + poprawny JWT; złe hasło (3x) → konsekwentnie `401`;
  `renew_loan("loan-002")` przesunął `duedate` z `20260812` na `20260826` (dokładnie +14 dni, zgodnie z
  REQ-13).

### Napotkana i wyjaśniona niestabilność tuż po pierwszym deployu

Bezpośrednio po pierwszym (nie kolejnym — **pierwszym w ogóle**) utworzeniu usługi, ok. 30-50% requestów
dostawało `404 Not Found` z nagłówkiem `x-render-routing: no-server` (odpowiedź z Cloudflare/edge Render,
`server: cloudflare`) zamiast realnej odpowiedzi aplikacji. Zdiagnozowane jako **czysto edge-routingowe, nie
błąd aplikacji**: te żądania w ogóle nie pojawiały się w logach aplikacji (`Logs` w dashboardzie), a
`Events` pokazywał tylko `First deploy started` → `Deploy live`, zero restartów/crashy. Po ~60 sekundach
odpytywania `/healthz` co 3s: 19/20 sukcesów (95%), po kolejnej minucie: 100%. Interpretacja: propagacja
routingu dla świeżo utworzonej subdomeny `*.onrender.com` na edge'u Render/Cloudflare, samo-naprawiająca się
w ciągu minuty-dwóch. **To nie jest to samo zjawisko co cold start po uśpieniu (patrz niżej) — to
jednorazowa rzecz przy pierwszym utworzeniu usługi, nie przy każdym wybudzeniu.**

## Cold start (Render free tier) — RYZYKO DLA GŁÓWNEGO CELU PROJEKTU

Render usypia darmowy serwis po ~15 min bezczynności; sam dashboard Render ostrzega wprost: *"Your free
instance will spin down with inactivity, which can delay requests by 50 seconds or more."*

- Zmierzony czas pierwszej odpowiedzi po uśpieniu: **nie zmierzony empirycznie w tej sesji** (wymagałoby
  ~15 minut realnej bezczynności przed testem, co wykracza poza pojedynczą turę tej rozmowy) — poniższa
  ocena ryzyka opiera się na **oficjalnym oszacowaniu samego Render** ("50 sekund lub więcej"), nie na
  domysłach.
- **Timeout klienta w `omnis-mobile` — sprawdzone bezpośrednio w kodzie
  (`OmnisRepository.createClient`, plik
  `app/src/main/kotlin/com/theundefined/omnis/data/repository/OmnisRepository.kt`), nie zgadywane:**
  `OkHttpClient.Builder()` jest tworzony BEZ żadnego wywołania `.connectTimeout()`/`.readTimeout()`/
  `.callTimeout()` (zero wystąpień słowa "Timeout" w całym module Kotlin — sprawdzone przez `grep -rn
  Timeout` na całym `app/src/main/kotlin/`). Obowiązują więc domyślne wartości OkHttp: **10 sekund** na
  connect i na read.
- **Czy timeout klienta > cold start? NIE.** 10s (timeout klienta) << 50s+ (własne oszacowanie Render).
  Realne ryzyko: jeśli instancja zdąży zasnąć między wdrożeniem a próbą logowania przez recenzenta Google
  Play, pierwsza próba logowania w apce prawdopodobnie zakończy się timeoutem połączenia, **zanim** Render
  w ogóle skończy budzić kontener — recenzent zobaczy błąd, nie ekran logowania. To bezpośrednio zagraża
  głównemu celowi tego projektu.
- **Rekomendowane opcje (żadna nie została wykonana samodzielnie — wymaga decyzji użytkownika):**
  1. **Podnieść timeout w `omnis-mobile`** (np. do 60-90s) w `OkHttpClient.Builder()` — najbardziej
     fundamentalna naprawa, ale to zmiana w osobnym projekcie/repo z własnym cyklem release'u (nowa wersja
     apki, nowy build do Play Console) — nie coś, co da się zrobić "przy okazji" tego wdrożenia.
  2. **Utrzymywać instancję "rozgrzaną"** przed/podczas okresu recenzji Google Play — np. zewnętrzny,
     darmowy cron (GitHub Actions scheduled workflow w tym samym repo, albo serwis typu cron-job.org)
     odpytujący `/healthz` co ~10 minut, żeby nigdy nie minęło 15 min bezczynności. Nie wymaga zmian w
     żadnym z projektów klienckich, tylko dodatkowej, osobnej konfiguracji (np. `.github/workflows/keepalive.yml`
     w tym repo) — do rozważenia jako osobne zadanie, jeśli użytkownik chce iść tą drogą.
  3. **Informacja w polu instrukcji testowych w Google Play Console** ("pierwsze logowanie może potrwać do
     minuty, spróbuj ponownie jeśli się nie uda") — najtańsze, ale nie eliminuje ryzyka, tylko je opisuje.
  4. Płatny plan Render (nie usypia) — jeśli akceptowalny koszt, eliminuje problem u źródła.

**To pozostaje otwarte — nie została podjęta decyzja, którą opcję wybrać.**

## Własna domena — rozważona i odrzucona

Rozważano CNAME `unofficial-omnis.aramin.net` → `omnis-mock.onrender.com`. Świadomie zrezygnowano: brak
realnej korzyści funkcjonalnej (rozróżnienie "nieoficjalne" jest w nazwie tenanta widocznej w apce, nie w
domenie), jedyna faktyczna zaleta własnej domeny — przenośność między dostawcami hostingu — nie była warta
dodatkowego kroku na tym etapie. Do ewentualnego ponownego rozważenia, jeśli/gdy dojdzie do zmiany dostawcy
(patrz opcje w sekcji cold-start wyżej). Docelowy, trwały URL to https://omnis-mock.onrender.com.

## Werdykt

- [x] Serwis żywy i działający poprawnie (smoke test PASS)
- [x] Własna domena — zamknięte, nie planowana (patrz wyżej)
- [ ] **Wymaga decyzji użytkownika przed użyciem jako konto testowe w Google Play Console**: ryzyko
  cold-start vs. timeout klienta (patrz wyżej) — bez tego recenzent może trafić na losowy błąd logowania
