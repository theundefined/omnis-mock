# DEPLOY_NOTES.md

Wypełnia subagent `devops` w Fazie 4 z `docs/PLAN.md`. Nie zaczynać tej fazy bez PASS w `docs/QA_REPORT.md`.

## Wdrożenie

- Publiczny URL (Render): _(wypełnić)_
- Data wdrożenia: _(wypełnić)_
- Zmienne środowiskowe ustawione w Render: _(wypełnić — bez wklejania realnych wartości, jeśli kiedyś
  przestaną być "niesekretne")_

## Smoke test na żywo

Ten sam scenariusz co `tests/test_contract.py`, uruchomiony przeciwko publicznemu URL-owi.

- Wynik: _(PASS/FAIL + szczegóły)_

## Cold start (Render free tier)

Render usypia serwis po ~15 min bezczynności.

- Zmierzony czas pierwszej odpowiedzi po uśpieniu: _(wypełnić, sekundy)_
- Timeout klienta w `omnis-mobile` (`OmnisRepository.createClient`, OkHttp connect/read timeout — sprawdzić
  plik, nie zgadywać): _(wypełnić)_
- Czy timeout klienta > zmierzony cold start?: _(TAK/NIE)_
- Jeśli NIE — ryzyko i rekomendowane opcje (bez samodzielnej zmiany kodu klienta):
  1. _(np. podniesienie timeoutu w apce — wymaga zgody użytkownika i osobnej zmiany w `omnis-mobile`)_
  2. _(np. "obudzenie" serwisu przed wysłaniem apki do recenzji Google Play)_
  3. _(np. informacja w polu instrukcji testowych w Google Play Console o możliwym opóźnieniu)_

## CNAME — do wykonania przez użytkownika (devops nie ma dostępu do DNS)

- Rekord: `unofficial-omnis.aramin.net` → _(dokładny target z Render, np. `xxxxx.onrender.com`)_
- Typ rekordu: CNAME
- Gdzie ustawić: panel DNS domeny `aramin.net`

## Werdykt

- [ ] Gotowe do użycia jako konto testowe w Google Play Console
- [ ] Wymaga działania użytkownika (CNAME i/lub decyzja o cold-startcie) przed użyciem
