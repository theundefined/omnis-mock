"""Punkt wejścia FastAPI. Endpointy i dokładny kształt JSON: docs/SPEC.md (REQ-1..REQ-14).

Layer 1 zaimplementowane w Fazie 1 (docs/PLAN.md). `/healthz`, `/discovery/search` i
`/primaws/rest/pub/pnxs` nie wymagały decyzji projektowych (bezpieczniki), reszta korzysta z `auth.py`/`data.py`.
"""

from fastapi import FastAPI, HTTPException, Request, Response

from omnis_mock import __version__, auth, data

app = FastAPI(title="omnis-mock", version=__version__)


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
