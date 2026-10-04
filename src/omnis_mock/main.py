"""Punkt wejścia FastAPI. Endpointy i dokładny kształt JSON: docs/SPEC.md (REQ-1..REQ-18b, REQ-G1..G5).

Layer 1 (login/counters/loans/renew) zaimplementowane w Fazie 1 (docs/PLAN.md), korzysta z
`auth.py`/`data.py`. Layer 2 (wyszukiwarka katalogu — `pnxs`/`delivery`/`getPhysicalService`/
`ILSServices/holdings`) zaimplementowane w Fazie 3, korzysta z `search_data.py`; pełna lista pól per
endpoint i uzasadnienie ich włączenia/wykluczenia względem realnego Primo: docs/API_FIELDS.md.
Anonimowe wyszukiwanie (token gościa z `guestJwt`, REQ-G1..G5) — wyszukiwarka nie wymaga żadnego tokena,
`myaccount/*` z tokenem gościa zwraca 200 z `"status": "failed"` (REQ-G3).

`/`, `/robots.txt` — strona statusu dla ludzi/botów, nie część kontraktu Primo (SPEC.md, sekcja
"Endpointy pomocnicze").
"""

import json
import os
import time
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

from omnis_mock import __version__, auth, data, search_data

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


@app.get("/primaws/rest/pub/institution/{institution}/guestJwt")
async def guest_jwt(institution: str, request: Request) -> Response:
    """SPEC.md REQ-G1 — token gościa do anonimowego wyszukiwania. Body to LITERAŁ stringu JSON (token w
    cudzysłowach), nie obiekt `{"jwtData": ...}` jak w `suprimaLogin`; Content-Type z jawnym charsetem
    (`JSONResponse` dałby samo `application/json`). Brak `viewId` -> 400 z pustym body.
    """
    view_id = request.query_params.get("viewId")
    if not view_id:
        return Response(status_code=400)
    language = request.query_params.get("lang") or "en"
    token = auth.issue_guest_token(institution, view_id, language)
    auth.register_guest_token(token)
    return Response(content=json.dumps(token), media_type="application/json;charset=UTF-8")


# REQ-G4: `MyInstitution` wysyła omnis-mobile od wersji z anonimowym wyszukiwaniem, `MyInstitution2`
# omnis-py i starsze omnis-mobile — oba muszą działać.
_KNOWN_SCOPES = {"MyInstitution", "MyInstitution2"}


@app.get("/primaws/rest/pub/pnxs", response_model=None)
async def pnxs_search(request: Request) -> dict | Response:
    """SPEC.md REQ-14/REQ-15/REQ-16 — wyszukiwarka katalogu (Layer 2). `qInclude` -> group expansion
    (wszystkie wydania danego `frbrgroupid`), inaczej top-level search po `q` (paginowany `offset`/`limit`).
    Zapytanie niczego nie trafiające zwraca `{"docs": []}` — dokładnie zachowanie REQ-14 sprzed Layer 2.
    Nie wymaga tokena (REQ-G2) — działa tak samo bez nagłówka, z tokenem gościa i z tokenem z logowania.
    """
    # REQ-G4: nieznany `scope` -> 400 z PUSTYM body (tak odpowiada Primo; HTTPException dałby
    # `{"detail": ...}`). Brak parametru albo pusty -> jak dotąd.
    scope = request.query_params.get("scope", "")
    if scope and scope not in _KNOWN_SCOPES:
        return Response(status_code=400)
    q = request.query_params.get("q", "")
    q_include = request.query_params.get("qInclude", "")
    offset = int(request.query_params.get("offset") or "0")
    limit = int(request.query_params.get("limit") or "10")
    docs, total = search_data.search(q, q_include, offset, limit)
    return {
        "docs": docs,
        "info": {
            "totalResultsLocal": total,
            "totalResultsPC": -1,
            "total": total,
            "first": offset + 1 if docs else 0,
            "last": offset + len(docs),
        },
    }


@app.get("/primaws/rest/pub/pnxs/L/{record_id}")
async def pnxs_record(record_id: str) -> dict:
    """SPEC.md REQ-G6 — pełny rekord (`pnx` + `delivery.holding`), bez tokena. omnis-mobile bierze stąd
    serię i autora wypożyczeń oraz adres filii, omnis-py — `get_record_details`. Nieznany rekord -> 200 z
    pustą kopertą wyszukiwania BEZ `pnx` (tak odpowiada prawdziwe Primo, NIE 404 — omnis-mobile zapisuje to
    jako "sprawdzone, bez serii")."""
    found = search_data.record(record_id)
    if found is None:
        return {"info": {"total": 0, "first": 0, "last": 0}, "facets": [], "docs": []}
    return found


@app.post("/primaws/rest/pub/delivery")
async def pnxs_delivery(request: Request) -> list:
    """SPEC.md REQ-17 — dostępność per filia dla podanych alma-id. Body to goła lista stringów JSON
    (klient wysyła `json=alma_ids` bezpośrednio, nie model), stąd `request.json()` zamiast typu Pydantic.
    """
    alma_ids = await request.json()
    return search_data.delivery(alma_ids)


@app.get("/primaws/rest/pub/getPhysicalService/{bare_mmsid}")
async def get_physical_service(bare_mmsid: str) -> dict:
    """SPEC.md REQ-18 — id usługi fizycznej, potrzebne do rozwiązania terminu zwrotu niedostępnego
    egzemplarza. Nieznany mmsid -> 404 (klient łapie to jako httpx.HTTPError -> None, patrz client.py)."""
    service_id = search_data.physical_service_id(bare_mmsid)
    if service_id is None:
        raise HTTPException(status_code=404, detail="Unknown record")
    return {"physicalServiceId": service_id}


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


# SPEC.md REQ-G3 — dokładne body prawdziwego Primo dla tokena gościa na `myaccount/*`. Status 200, NIE 401.
_GUEST_PATRON_INVALID = {
    "beaconO22": "0",
    "status": "failed",
    "reply-code": "0002",
    "reply-text": "The patron ID is invalid",
    "data": None,
}


def _require_patron(request: Request) -> Optional[JSONResponse]:
    """Autoryzacja endpointów `myaccount/*`: token z logowania -> `None` (obsłuż normalnie); token gościa ->
    gotowa odpowiedź 200 "failed" do zwrócenia (REQ-G3, pułapka: klient sprawdzający tylko kod HTTP uzna ją
    za sukces); brak/nieznany token -> 401 (REQ-5/REQ-8/REQ-12)."""
    kind = auth.token_kind(request.headers.get("Authorization"))
    if kind == "login":
        return None
    if kind == "guest":
        return JSONResponse(_GUEST_PATRON_INVALID)
    raise HTTPException(status_code=401, detail="Not authenticated")


@app.get("/primaws/rest/priv/myaccount/counters", response_model=None)
async def counters(request: Request) -> dict | JSONResponse:
    """SPEC.md REQ-5, REQ-6, REQ-7 — UWAGA REQ-7: format kwoty z KROPKĄ ("0.00"), inny niż w /fines."""
    if (denied := _require_patron(request)) is not None:
        return denied
    return {"data": {"listofactions": {"action": data.get_demo_counters()}}}


@app.get("/primaws/rest/priv/myaccount/loans", response_model=None)
async def loans(request: Request, type: str = "active") -> dict | JSONResponse:
    """SPEC.md REQ-8, REQ-9, REQ-10, REQ-11, REQ-L1, REQ-L4 — UWAGA REQ-11: showmore nie może zawiesić
    klienta w pętli (dotyczy też historii). `type=history` -> osobna lista zakończonych wypożyczeń, każda inna
    wartość (albo brak) -> aktywne."""
    if (denied := _require_patron(request)) is not None:
        return denied
    loan_list = data.get_demo_history() if type == "history" else data.get_demo_loans()
    return {"data": {"loans": {"loan": loan_list, "showmore": [], "historicloans": "Y", "hasAlerts": False}}}


@app.post("/primaws/rest/priv/myaccount/renew_loans", response_model=None)
async def renew_loans(request: Request) -> dict | JSONResponse:
    """SPEC.md REQ-12, REQ-13, REQ-13b — nieznany id to no-op 200, nie błąd. Token gościa -> REQ-G3, bez
    mutacji stanu."""
    if (denied := _require_patron(request)) is not None:
        return denied
    body = await request.json()
    loan_id = str(body.get("id", ""))
    renewed = data.renew_demo_loan(loan_id)
    return {"success": True, "renewed": renewed}


@app.post("/primaws/rest/priv/ILSServices/holdings/{physical_service_id}")
async def ils_holdings(physical_service_id: str, request: Request) -> dict:
    """SPEC.md REQ-18b (pułapka) — termin zwrotu dla niedostępnego egzemplarza. Zwraca dane TYLKO gdy
    body zawiera niepusty `holKey` w `locations[0]` (replikuje empirycznie zweryfikowane zachowanie
    realnego Primo) — inaczej 200 z pustą listą `items`, NIE 404, dokładnie jak prawdziwe API.

    Mimo ścieżki `priv` CELOWO nie sprawdza `Authorization` (REQ-G2): prawdziwe Primo odpowiada tu tak samo
    bez tokena, z tokenem gościa i z tokenem z logowania — nagłówek jest w całości ignorowany.
    """
    body = await request.json()
    locations = body.get("locations") or []
    request_holding = locations[0] if locations else None
    location = search_data.holding_items(physical_service_id, request_holding)
    if location is None:
        return {"data": {"itemInfo": {"locations": []}}}
    return {"data": {"itemInfo": {"locations": [location]}}}


# --- Zamówienia (rezerwacje), SPEC.md REQ-H4..REQ-H12 -------------------------------------------------------

# REQ-H4: sześć kategorii, zawsze wszystkie; pięć ostatnich zawsze puste (kształt elementu nieznany).
_EMPTY_REQUEST_CATEGORIES = {
    "photocopies": {"photocopy": []},
    "bookings": {"booking": []},
    "cdls": {"cdl": []},
    "ills": {"ill": []},
    "acqs": {"acq": []},
}


@app.get("/primaws/rest/priv/myaccount/requests", response_model=None)
async def my_requests(request: Request) -> dict | JSONResponse:
    """SPEC.md REQ-H4/REQ-H5 — lista zamówień. Token gościa -> REQ-G3 (200 "failed")."""
    if (denied := _require_patron(request)) is not None:
        return denied
    return {"data": {"holds": {"hold": data.get_demo_holds()}, **_EMPTY_REQUEST_CATEGORIES}}


@app.post("/primaws/rest/priv/myaccount/cancel_requests", response_model=None)
async def cancel_requests(request: Request) -> dict | JSONResponse:
    """SPEC.md REQ-H11 (pułapka) — `request_type` musi być dokładnie `"holds"` (liczba mnoga). Inny typ albo
    nieznany id -> 200 bez zmiany stanu (jak REQ-13b), z tą samą kopertą sukcesu i pustą listą."""
    if (denied := _require_patron(request)) is not None:
        return denied
    body = await request.json()
    request_id = str(body.get("request_id", ""))
    cancelled = body.get("request_type") == "holds" and data.cancel_demo_hold(request_id)
    holds = [{"requestid": request_id, "note": {"type": "info"}}] if cancelled else []
    return {
        "beaconO22": "646",
        "status": "ok",
        "reply-code": "0000",
        "reply-text": "OK",
        "data": {"holds": {"hold": holds}},
    }


def _require_login_token(request: Request) -> None:
    """`ILSServices/itemServices` i `itemQueue`: tylko token z logowania, inaczej 401 (REQ-H10; zachowanie
    prawdziwego Primo dla gościa jest niezweryfikowane)."""
    if auth.token_kind(request.headers.get("Authorization")) != "login":
        raise HTTPException(status_code=401, detail="Not authenticated")


@app.get(
    "/primaws/rest/priv/ILSServices/itemServices/{mmsid}/item/{item_id}/{psid}/AlmaItemRequest",
    response_model=None,
)
async def item_request_form(mmsid: str, item_id: str, psid: str, request: Request) -> dict:
    """SPEC.md REQ-H10a — formularz zamówienia (miejsca odbioru w formacie `<libraryId>$$<TYPE>`). Egzemplarz
    nieznany albo `allowed: "N"` -> 400."""
    _require_login_token(request)
    form = search_data.item_form(item_id)
    if form is None:
        raise HTTPException(status_code=400, detail="Item cannot be requested")
    return form


@app.post(
    "/primaws/rest/priv/ILSServices/itemServices/{mmsid}/item/{item_id}/{psid}/AlmaItemRequest",
    response_model=None,
)
async def item_request_place(mmsid: str, item_id: str, psid: str, request: Request) -> dict:
    """SPEC.md REQ-H10b — złożenie zamówienia. Odpowiedź to goła koperta BEZ `requestid` (zweryfikowana na
    żywo); `pickupLocation` spoza formularza albo nieznany `itemId` -> 400. Mock dodaje zamówienie od razu
    (prawdziwe Primo z kilkusekundowym opóźnieniem — `omnis-py` i tak ponawia odczyt)."""
    _require_login_token(request)
    try:
        body = await request.json()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid JSON") from None
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Invalid body")
    body_item_id = str(body.get("itemId", ""))
    info = search_data.catalog_hold_info(search_data.item_mmsid(body_item_id) or "", body_item_id)
    if info is None or not info["allowed"] or body.get("requestType") != "hold":
        raise HTTPException(status_code=400, detail="Item cannot be requested")
    pickup = next((p for p in info["pickups"] if p["id"] == body.get("pickupLocation")), None)
    if pickup is None or (body.get("pickupLibraryId") not in (None, pickup["id"])):
        raise HTTPException(status_code=400, detail="Invalid pickup location")
    data.place_demo_hold(info["mmsid"], info["item_id"], info["title"], info["author"], pickup["name"])
    return {"beaconO22": "646", "reply-text": "ok", "status": "ok"}


@app.get("/primaws/rest/priv/ILSServices/itemQueue/{item_id}", response_model=None)
async def item_queue(item_id: str, request: Request) -> dict:
    """SPEC.md REQ-H12 — kolejka zamówień na egzemplarz. Wymaga tokena z logowania (spójnie z
    `itemServices`); nieznany egzemplarz -> 404."""
    _require_login_token(request)
    if search_data.item_mmsid(item_id) is None:
        raise HTTPException(status_code=404, detail="Unknown item")
    return {"itemId": item_id, "itemQueueString": f"(zamówienie: {data.hold_queue_length(item_id)})"}
