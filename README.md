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

Szkielet + kompletna specyfikacja/plan. Implementacja endpointów jeszcze nie istnieje — `pytest` jest celowo
czerwony do czasu Fazy 1 (patrz `docs/PLAN.md`).

## Zacznij tutaj

- **`docs/SPEC.md`** — kontrakt API: dokładny kształt JSON per endpoint, wymagane pola, znane pułapki.
  Jedyne źródło prawdy o tym, CO zbudować.
- **`docs/PLAN.md`** — fazowy plan realizacji z rolami `developer`/`qa`/`devops` (zdefiniowanymi jako custom
  subagenty w `.claude/agents/`), kryteriami wyjścia z każdej fazy.
- **`tests/test_contract.py`** — już napisany, celowo czerwony: uruchamia prawdziwy `OmnisClient` z
  opublikowanej paczki `omnis-py` przeciwko temu serwerowi. Zielony = kontrakt spełniony.

## Szybki start (lokalnie)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

uvicorn omnis_mock.main:app --reload   # http://localhost:8000
pytest -v                              # w drugim terminalu
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
