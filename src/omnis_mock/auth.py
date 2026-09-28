"""Fake JWT + rejestry ważnych tokenów. Kontrakt: docs/SPEC.md REQ-4 (login), REQ-5/REQ-8/REQ-12 (auth
na endpointach prywatnych) oraz REQ-G1/REQ-G3 (token gościa). Zaimplementowane w Fazie 1 (docs/PLAN.md),
token gościa dodany w ramach REQ-G1..G5.

Dwa OSOBNE rejestry: tokeny z `suprimaLogin` (dostęp do konta) i tokeny gościa z `guestJwt` (tylko
wyszukiwarka — na `myaccount/*` dostają odpowiedź "failed", REQ-G3). `token_kind()` rozróżnia oba.
"""

import base64
import json
import time
from datetime import datetime
from typing import Literal, Optional

_valid_tokens: set[str] = set()
_guest_tokens: set[str] = set()

# Czas życia tokena gościa w payloadzie (`exp - iat`) — tyle, ile wydaje prawdziwe Primo (24h). Mock nie
# sprawdza `exp` (tokeny z logowania też nie wygasają) — pole jest tylko dla wierności kształtu.
_GUEST_TOKEN_TTL_SECONDS = 86400


def _b64_encode_no_pad(payload: bytes) -> str:
    """Standardowy alfabet base64 (+/), CELOWO NIE urlsafe (-_).

    omnis-py dekoduje payload JWT przez zwykłe `base64.b64decode(...)`, które przy `validate=False`
    (domyślne) po cichu ODRZUCA znaki spoza standardowego alfabetu zamiast rzucić błąd — token zakodowany
    jako urlsafe base64 (z `-`/`_`) zostałby więc bezgłośnie okaleczony przed `json.loads`, zamiast czytelnie
    się wywalić. Padding usuwamy, bo klient sam go dokłada przed dekodowaniem (patrz client.py).
    """
    return base64.b64encode(payload).rstrip(b"=").decode("ascii")


def issue_token(display_name: str, user_name: str) -> str:
    """Fake JWT: `header.payload.signature`, dokładnie 3 segmenty (SPEC.md REQ-4).

    `display_name`/`user_name` MUSZĄ być czystym ASCII — patrz uzasadnienie w docs/SPEC.md REQ-4.
    """
    header = _b64_encode_no_pad(json.dumps({"alg": "none", "typ": "JWT"}).encode("ascii"))
    payload = _b64_encode_no_pad(json.dumps({"displayName": display_name, "userName": user_name}).encode("ascii"))
    signature = _b64_encode_no_pad(b"mock-signature-not-verified-by-any-client")
    return f"{header}.{payload}.{signature}"


def issue_guest_token(institution: str, view_id: str, language: str) -> str:
    """Fake JWT gościa (SPEC.md REQ-G1) — ten sam format i kodowanie co `issue_token()` (REQ-4), payload z
    kluczowymi polami prawdziwego tokena gościa Primo (`userGroup: "GUEST"`, `displayName: null`).

    `institution`/`view_id`/`language` pochodzą z żądania, więc mogą nie być ASCII — `json.dumps` z
    domyślnym `ensure_ascii=True` zamienia je na escape'y `\\uXXXX`, więc payload zostaje czystym ASCII.
    """
    now = int(time.time())
    user = f"anonymous-{datetime.now().strftime('%m%d_%H%M%S')}"
    claims = {
        "iss": "Prima",
        "userName": user,
        "user": user,
        "displayName": None,
        "userGroup": "GUEST",
        "institution": institution,
        "viewId": view_id,
        "signedIn": None,
        "onCampus": "false",
        "language": language,
        "iat": now,
        "exp": now + _GUEST_TOKEN_TTL_SECONDS,
    }
    header = _b64_encode_no_pad(json.dumps({"alg": "none", "typ": "JWT"}).encode("ascii"))
    payload = _b64_encode_no_pad(json.dumps(claims).encode("ascii"))
    signature = _b64_encode_no_pad(b"mock-signature-not-verified-by-any-client")
    return f"{header}.{payload}.{signature}"


def register_token(token: str) -> None:
    """Zapamiętuje `token` jako ważny token z logowania (rejestr in-memory, per proces)."""
    _valid_tokens.add(token)


def register_guest_token(token: str) -> None:
    """Zapamiętuje `token` jako ważny token gościa — osobno od tokenów z logowania (SPEC.md REQ-G1/REQ-G3)."""
    _guest_tokens.add(token)


def _bearer(authorization_header: Optional[str]) -> Optional[str]:
    if not authorization_header or not authorization_header.startswith("Bearer "):
        return None
    return authorization_header[len("Bearer ") :]


def token_kind(authorization_header: Optional[str]) -> Optional[Literal["login", "guest"]]:
    """`"login"` / `"guest"` dla zarejestrowanego tokena z `Authorization: Bearer <token>`, `None` dla braku
    nagłówka albo nieznanego tokena."""
    token = _bearer(authorization_header)
    if token is None:
        return None
    if token in _valid_tokens:
        return "login"
    if token in _guest_tokens:
        return "guest"
    return None


def is_valid_token(authorization_header: Optional[str]) -> bool:
    """`Authorization: Bearer <token>` względem tokenów z LOGOWANIA (`register_token()`) — token gościa
    tu nie przechodzi."""
    return token_kind(authorization_header) == "login"


def reset_state() -> None:
    """Czyści rejestry wydanych tokenów (używane przez testy dla deterministyczności)."""
    _valid_tokens.clear()
    _guest_tokens.clear()
