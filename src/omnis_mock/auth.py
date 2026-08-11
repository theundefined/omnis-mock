"""Fake JWT + rejestr ważnych tokenów. Kontrakt: docs/SPEC.md REQ-4 (login) oraz REQ-5/REQ-8/REQ-12 (auth
na endpointach prywatnych). Zaimplementowane w Fazie 1 (docs/PLAN.md).
"""

import base64
import json
from typing import Optional

_valid_tokens: set[str] = set()


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


def register_token(token: str) -> None:
    """Zapamiętuje `token` jako ważny (rejestr in-memory, per proces)."""
    _valid_tokens.add(token)


def is_valid_token(authorization_header: Optional[str]) -> bool:
    """`Authorization: Bearer <token>` względem tokenów zarejestrowanych przez `register_token()`."""
    if not authorization_header or not authorization_header.startswith("Bearer "):
        return False
    token = authorization_header[len("Bearer ") :]
    return token in _valid_tokens


def reset_state() -> None:
    """Czyści rejestr wydanych tokenów (używane przez testy dla deterministyczności)."""
    _valid_tokens.clear()
