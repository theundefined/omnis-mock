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
