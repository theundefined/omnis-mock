"""Fixture danych demo-konta. Kontrakt: docs/SPEC.md, sekcja "Dane demo" + REQ-6/REQ-7/REQ-9/REQ-10/REQ-11/REQ-13.

Zaimplementowane w Fazie 1 (docs/PLAN.md). Tytuły z domeny publicznej (polska klasyka) — patrz SPEC.md.
"""

import os
from datetime import date, timedelta
from typing import Any, Optional

DEMO_USERNAME = os.environ.get("DEMO_USERNAME", "demo")
DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "demo1234")

# ASCII-only celowo — SPEC.md REQ-4: displayName trafia do JWT payload, a Python (omnis-py) i
# Kotlin (omnis-mobile) dekodują base64 różnymi ścieżkami; polskie znaki diakrytyczne to najłatwiejszy
# sposób, żeby te dwie implementacje dały różny wynik.
_DEMO_DISPLAY_NAME = "Demo User"

# Statyczne "szablony" wypożyczeń: due_offset_days/loan_offset_days są WZGLĘDEM date.today() w momencie
# odpowiedzi (SPEC.md: "nie hardkodować absolutnych dat") — jedyny mutowalny stan to _renewal_extensions.
_LOAN_TEMPLATES: list[dict[str, Any]] = [
    {
        "loanid": "loan-001",
        "mmsid": "mock-mms-001",
        "title": "Pan Tadeusz",
        "author": "Adam Mickiewicz",
        "due_offset_days": 5,
        "loan_offset_days": -25,
        "duehour": "23:59",
        "loanstatus": "Active",
        "ilsinstitutionname": "Nieoficjalna Biblioteka OMNIS (Demo)",
        "mainlocationname": "Filia Demo 1",
        "secondarylocationname": None,
        "itembarcode": "DEMO0001",
        "renew": "Y",
    },
    {
        "loanid": "loan-002",
        "mmsid": "mock-mms-002",
        "title": "Lalka",
        "author": "Bolesław Prus",
        "due_offset_days": -3,  # przeterminowane — SPEC.md "Dane demo" wymaga >=1 takiego
        "loan_offset_days": -33,
        "duehour": "23:59",
        "loanstatus": "Active",
        "ilsinstitutionname": "Nieoficjalna Biblioteka OMNIS (Demo)",
        "mainlocationname": "Filia Demo 2",
        "secondarylocationname": None,
        "itembarcode": "DEMO0002",
        "renew": "Y",
    },
    {
        "loanid": "loan-003",
        "mmsid": "mock-mms-003",
        "title": "Quo Vadis",
        "author": "Henryk Sienkiewicz",
        "due_offset_days": 20,
        "loan_offset_days": -10,
        "duehour": "23:59",
        "loanstatus": "Active",
        "ilsinstitutionname": "Nieoficjalna Biblioteka OMNIS (Demo)",
        "mainlocationname": "Filia Demo 1",
        "secondarylocationname": None,
        "itembarcode": "DEMO0003",
        "renew": "N",  # nie-odnawialne — SPEC.md "Dane demo" wymaga >=1 takiego
    },
    {
        "loanid": "loan-004",
        "mmsid": "mock-mms-004",
        "title": "Dziady",
        "author": "Adam Mickiewicz",
        "due_offset_days": 1,
        "loan_offset_days": -29,
        "duehour": "23:59",
        "loanstatus": "Active",
        "ilsinstitutionname": "Nieoficjalna Biblioteka OMNIS (Demo)",
        "mainlocationname": "Filia Demo 3",
        "secondarylocationname": None,
        "itembarcode": "DEMO0004",
        "renew": "Y",
    },
]

# loan_id -> dodatkowe dni doliczone przez renew_demo_loan(); resetowane przez reset_state().
_renewal_extensions: dict[str, int] = {}


def _format_date(value: date) -> str:
    return value.strftime("%Y%m%d")


def get_demo_counters() -> list[dict[str, str]]:
    """`data.listofactions.action` dla `GET /myaccount/counters` (SPEC.md REQ-6/REQ-7).

    `Fines` w formacie Z KROPKĄ ("0.00") — REQ-7, inny format niż w /fines (poza zakresem Layer 1).
    """
    loans = get_demo_loans()
    return [
        {"type": "Loans", "value": str(len(loans))},
        {"type": "Requests", "value": "0"},
        {"type": "Fines", "value": "0.00"},
    ]


def get_demo_loans() -> list[dict[str, Any]]:
    """Aktualna lista wypożyczeń (SPEC.md REQ-9, REQ-10, REQ-11) — daty liczone na bieżąco względem dziś,
    z uwzględnieniem ewentualnych prolongat (`_renewal_extensions`).
    """
    today = date.today()
    result = []
    for tmpl in _LOAN_TEMPLATES:
        extension_days = _renewal_extensions.get(tmpl["loanid"], 0)
        due_date = today + timedelta(days=tmpl["due_offset_days"] + extension_days)
        loan_date = today + timedelta(days=tmpl["loan_offset_days"])
        result.append(
            {
                "loanid": tmpl["loanid"],
                "mmsid": tmpl["mmsid"],
                "title": tmpl["title"],
                "author": tmpl["author"],
                "duedate": _format_date(due_date),
                "duehour": tmpl["duehour"],
                "loandate": _format_date(loan_date),
                "loanstatus": tmpl["loanstatus"],
                "ilsinstitutionname": tmpl["ilsinstitutionname"],
                "mainlocationname": tmpl["mainlocationname"],
                "secondarylocationname": tmpl["secondarylocationname"],
                "itembarcode": tmpl["itembarcode"],
                "renew": tmpl["renew"],
            }
        )
    return result


def renew_demo_loan(loan_id: str) -> bool:
    """SPEC.md REQ-13/REQ-13b: znany `loan_id` -> +14 dni do terminu, zwraca True. Nieznany -> no-op, False."""
    known_ids = {tmpl["loanid"] for tmpl in _LOAN_TEMPLATES}
    if loan_id not in known_ids:
        return False
    _renewal_extensions[loan_id] = _renewal_extensions.get(loan_id, 0) + 14
    return True


def reset_state() -> None:
    """Resetuje prolongaty do stanu początkowego (używane przez tests/test_contract.py)."""
    _renewal_extensions.clear()


def check_credentials(username: str, password: str) -> Optional[dict[str, str]]:
    """SPEC.md REQ-1/REQ-3/REQ-4: zwraca dane do JWT jeśli to demo-konto, inaczej None (-> 401 w main.py)."""
    if username == DEMO_USERNAME and password == DEMO_PASSWORD:
        return {"displayName": _DEMO_DISPLAY_NAME, "userName": DEMO_USERNAME}
    return None
