# omnis-mock

Mock serwera Ex Libris Primo / OMNIS API — jedno stałe konto demo, fałszywe wypożyczenia, **zero** dostępu
do jakiejkolwiek prawdziwej biblioteki. Powstał, bo `omnis-mobile` (apka na Androida z tego workspace'u)
wymaga w Google Play danych logowania do testów, a autor nie jest administratorem sieci OMNIS — więc zamiast
podawać czyjeś prawdziwe dane logowania recenzentowi, wystawiamy publiczny, samowystarczalny mock.

Docelowo wdrożony pod `unofficial-omnis.aramin.net` — nazwa celowo jednoznacznie oznaczona jako
"nieoficjalna", żeby nie sugerować związku z realną siecią OMNIS.

Część większego ekosystemu opisanego w `../CLAUDE.md` (workspace `bracz`): `omnis-py` jest źródłem prawdy o
kształcie prawdziwego API Primo, ten projekt go odzwierciedla po stronie serwera dla celów testowych/demo.

## Status

**Layer 1 zaimplementowany, przetestowany (QA: PASS, `docs/QA_REPORT.md`) i wdrożony:
https://omnis-mock.onrender.com.** Layer 2 (pełna wyszukiwarka katalogu) to opcjonalna, nie zaczęta jeszcze
Faza 3 — patrz `docs/PLAN.md`. Znane, nierozwiązane jeszcze ryzyko: cold start darmowego tieru Render vs.
timeout klienta w `omnis-mobile` — patrz `docs/DEPLOY_NOTES.md`.

## Zacznij tutaj

- **`docs/SPEC.md`** — kontrakt API: dokładny kształt JSON per endpoint, wymagane pola, znane pułapki.
  Jedyne źródło prawdy o tym, CO ten serwer robi.
- **`docs/PLAN.md`** — fazowy plan realizacji z rolami `developer`/`qa`/`devops` (zdefiniowanymi jako custom
  subagenty w `.claude/agents/`), kryteriami wyjścia z każdej fazy.
- **`docs/QA_REPORT.md`** / **`docs/DEPLOY_NOTES.md`** — wynik niezależnej weryfikacji i stan wdrożenia.
- **`tests/test_contract.py`** — uruchamia prawdziwy `OmnisClient` z opublikowanej paczki `omnis-py`
  przeciwko temu serwerowi. Zielony = kontrakt spełniony (silniejszy test niż ręczne assercje).

## Szybki start (lokalnie)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

uvicorn omnis_mock.main:app --reload   # http://localhost:8000
pytest -v                              # w drugim terminalu
```

## Ręczne testowanie API

- **`scripts/curl/`** — gotowe skrypty `curl`, po jednym na endpoint/REQ z `docs/SPEC.md`, plus
  `run_all.sh` z podsumowaniem PASS/FAIL. Działają przeciwko `localhost` albo (ustawiając `BASE_URL`)
  przeciwko żywemu deployowi na Render. Szczegóły: `scripts/curl/README.md`.
- **`scripts/setup_demo_client.sh`** — tworzy izolowany venv z prawdziwym `omnis-py` z PyPI,
  skonfigurowanym pod tego mocka (`omnis-cli` gotowe do użycia bez dotykania prawdziwego
  `~/.config/omnis-py/config.yaml`):
  ```bash
  ./scripts/setup_demo_client.sh                                   # przeciwko localhost:8000
  ./scripts/setup_demo_client.sh https://omnis-mock.onrender.com   # przeciwko żywemu deployowi
  ./demo-client/bin/omnis-cli-demo --renew
  ```

## Dlaczego Render (darmowy hosting)

Python/FastAPI natywnie przez Docker, bez wymogu karty kredytowej, darmowa własna domena, auto-deploy z
GitHub. Jedyny kompromis: usypianie po ~15 min bezczynności (cold start przy pierwszym żądaniu) —
akceptowalne dla endpointu używanego sporadycznie (recenzja Google Play, okazjonalni testerzy), ale
zweryfikowane wprost w `docs/PLAN.md` Faza 4 (porównanie z timeoutami klienta w `omnis-mobile`).

## Bezpieczeństwo

- Jedno stałe konto demo — złe dane logowania zawsze zwracają `401` (mirror prawdziwego zachowania Primo);
  mock nie akceptuje dowolnych danych jako "zalogowany".
- Zero prawdziwych danych osobowych, zero wywołań do prawdziwego Primo/OpenLibrary z wnętrza mocka.
- Stan (np. po prolongacie) trzymany wyłącznie w pamięci procesu — restart czyści wszystko.
