"""Punkt wejścia FastAPI. Endpointy i dokładny kształt JSON: docs/SPEC.md (REQ-1..REQ-14).

Layer 1 zaimplementowane w Fazie 1 (docs/PLAN.md). `/healthz`, `/discovery/search` i
`/primaws/rest/pub/pnxs` nie wymagały decyzji projektowych (bezpieczniki), reszta korzysta z `auth.py`/`data.py`.

`/`, `/robots.txt` — strona statusu dla ludzi/botów, nie część kontraktu Primo (SPEC.md, sekcja
"Endpointy pomocnicze").
"""

import os
import time

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, PlainTextResponse

from omnis_mock import __version__, auth, data

app = FastAPI(title="omnis-mock", version=__version__)

_START_TIME = time.monotonic()
_GITHUB_URL = "https://github.com/theundefined/omnis-mock"
# Render ustawia to automatycznie w środowisku wdrożenia; lokalnie po prostu brak.
_COMMIT = os.environ.get("RENDER_GIT_COMMIT", "")


def _uptime_str() -> str:
    total_seconds = int(time.monotonic() - _START_TIME)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def _external_base_url(request: Request) -> str:
    """Base URL tak, jak widzi go świat na zewnątrz — z nagłówków X-Forwarded-Proto/-Host, jeśli obecne
    (Render/Cloudflare je ustawiają), inaczej z samego request.url. CELOWO nie hardkoduje żadnej domeny
    (Render czy innej) — ten sam kod pokazuje poprawny URL na localhost, na Render, i na jakimkolwiek
    przyszłym hostingu/domenie bez zmiany. Nie polega na `--proxy-headers` uvicorna (i jego zawężeniu do
    zaufanych IP), tylko czyta nagłówki wprost — prościej i przewidywalnie za dowolnym reverse proxy.
    """
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.headers.get("host", request.url.netloc))
    return f"{scheme}://{host}"


@app.get("/", response_class=HTMLResponse)
async def status_page(request: Request) -> str:
    """Strona statusu (SPEC.md, "Endpointy pomocnicze") — czysto informacyjna, nie testowana przez
    tests/test_contract.py. Pokazuje dane konta demo wprost (nie-sekret, patrz SPEC.md "Dane demo") razem
    z base_url wyliczonym z requestu (patrz _external_base_url), żeby ktokolwiek trafiający tu bezpośrednio
    miał komplet danych do skonfigurowania klienta bez szukania w dokumentacji.
    """
    base_url = _external_base_url(request)
    commit_html = (
        f'<a href="{_GITHUB_URL}/commit/{_COMMIT}"><code>{_COMMIT[:7]}</code></a>'
        if _COMMIT
        else "<code>dev</code> (środowisko lokalne)"
    )
    return f"""<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>omnis-mock — status</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 640px;
         margin: 3rem auto; padding: 0 1.5rem; line-height: 1.5; color: #1a1a1a; }}
  h1 {{ font-size: 1.4rem; }}
  h2 {{ font-size: 1.1rem; margin-top: 2rem; }}
  .badge {{ display: inline-block; background: #16a34a; color: white; border-radius: 999px;
            padding: 0.15rem 0.7rem; font-size: 0.8rem; font-weight: 600; vertical-align: middle; }}
  .warn {{ background: #fef3c7; border: 1px solid #f59e0b; border-radius: 8px; padding: 0.8rem 1rem;
           margin: 1rem 0; font-size: 0.9rem; }}
  dl {{ display: grid; grid-template-columns: auto 1fr; gap: 0.35rem 1rem; font-size: 0.9rem; margin: 0; }}
  dt {{ color: #666; }}
  dd {{ margin: 0; }}
  code {{ background: #f3f4f6; padding: 0.1rem 0.4rem; border-radius: 4px; }}
  a {{ color: #2563eb; }}
  footer {{ margin-top: 2rem; font-size: 0.8rem; color: #888; }}
</style>
</head>
<body>
  <h1>omnis-mock <span class="badge">running</span></h1>
  <p>Mock serwera Ex Libris Primo / OMNIS API — jedno stałe konto demo, fałszywe dane, zero dostępu do
  jakiejkolwiek prawdziwej biblioteki.</p>
  <div class="warn">To <strong>nie</strong> jest oficjalna sieć OMNIS ani żadna prawdziwa biblioteka —
  wyłącznie serwer testowy dla ekosystemu <code>omnis-py</code> / <code>omnis-mobile</code> /
  <code>omnis-android</code>.</div>

  <dl>
    <dt>Wersja</dt><dd><code>{__version__}</code></dd>
    <dt>Commit</dt><dd>{commit_html}</dd>
    <dt>Uptime</dt><dd>{_uptime_str()}</dd>
    <dt>Repo</dt><dd><a href="{_GITHUB_URL}">{_GITHUB_URL}</a></dd>
    <dt>Health check</dt><dd><a href="/healthz">/healthz</a></dd>
    <dt>Kontrakt API</dt><dd><a href="{_GITHUB_URL}/blob/main/docs/SPEC.md">docs/SPEC.md</a></dd>
  </dl>

  <h2>Konto demo</h2>
  <dl>
    <dt>Base URL</dt><dd><code>{base_url}</code></dd>
    <dt>Login</dt><dd><code>{data.DEMO_USERNAME}</code></dd>
    <dt>Hasło</dt><dd><code>{data.DEMO_PASSWORD}</code></dd>
    <dt>Institution / View</dt><dd><code>MOCK</code> / <code>MOCK:MOCK</code></dd>
  </dl>

  <footer>Darmowy tier Render usypia tę instancję po bezczynności — pierwsze żądanie po dłuższej przerwie
  może potrwać do ok. minuty.</footer>
</body>
</html>"""


@app.get("/robots.txt", response_class=PlainTextResponse)
async def robots_txt() -> str:
    """SPEC.md, "Endpointy pomocnicze" — publiczny mock pod ogólnodostępnym URL-em, nie chcemy indeksowania."""
    return "User-agent: *\nDisallow: /\n"


@app.get("/healthz")
async def healthz() -> dict:
    """Health check dla Render (docs/PLAN.md, Faza 4)."""
    return {"status": "ok"}


@app.get("/discovery/search")
async def discovery_search() -> Response:
    """Cookie-priming w prawdziwym Primo (SPEC.md REQ-2). Klient ignoruje treść — wystarczy 200."""
    return Response(status_code=200)


@app.get("/primaws/rest/pub/pnxs")
async def pnxs_stub() -> dict:
    """Bezpiecznik dla ekranu wyszukiwania w `omnis-mobile` (SPEC.md REQ-14) — Layer 2 to osobna faza."""
    return {"docs": []}


@app.post("/primaws/suprimaLogin")
async def suprima_login(request: Request) -> dict:
    """SPEC.md REQ-1, REQ-3, REQ-4 — logowanie demo-konta, wydanie fake JWT."""
    form = await request.form()
    username = str(form.get("username", ""))
    password = str(form.get("password", ""))

    credentials = data.check_credentials(username, password)
    if credentials is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = auth.issue_token(credentials["displayName"], credentials["userName"])
    auth.register_token(token)
    return {"jwtData": token}


def _require_valid_token(request: Request) -> None:
    if not auth.is_valid_token(request.headers.get("Authorization")):
        raise HTTPException(status_code=401, detail="Not authenticated")


@app.get("/primaws/rest/priv/myaccount/counters")
async def counters(request: Request) -> dict:
    """SPEC.md REQ-5, REQ-6, REQ-7 — UWAGA REQ-7: format kwoty z KROPKĄ ("0.00"), inny niż w /fines."""
    _require_valid_token(request)
    return {"data": {"listofactions": {"action": data.get_demo_counters()}}}


@app.get("/primaws/rest/priv/myaccount/loans")
async def loans(request: Request) -> dict:
    """SPEC.md REQ-8, REQ-9, REQ-10, REQ-11 — UWAGA REQ-11: showmore nie może zawiesić klienta w pętli."""
    _require_valid_token(request)
    return {"data": {"loans": {"loan": data.get_demo_loans(), "showmore": []}}}


@app.post("/primaws/rest/priv/myaccount/renew_loans")
async def renew_loans(request: Request) -> dict:
    """SPEC.md REQ-12, REQ-13, REQ-13b — nieznany id to no-op 200, nie błąd."""
    _require_valid_token(request)
    body = await request.json()
    loan_id = str(body.get("id", ""))
    renewed = data.renew_demo_loan(loan_id)
    return {"success": True, "renewed": renewed}
