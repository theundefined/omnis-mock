"""Fixture danych demo-konta. Kontrakt: docs/SPEC.md, sekcja "Dane demo" + REQ-6/REQ-7/REQ-9/REQ-10/REQ-11/REQ-13.

Zaimplementowane w Fazie 1 (docs/PLAN.md). Tytuły z domeny publicznej (polska klasyka) — patrz SPEC.md.
"""

import itertools
import os
from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Any, Optional

DEMO_USERNAME = os.environ.get("DEMO_USERNAME", "demo")
DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "demo1234")

# ASCII-only celowo — SPEC.md REQ-4: displayName trafia do JWT payload, a Python (omnis-py) i
# Kotlin (omnis-mobile) dekodują base64 różnymi ścieżkami; polskie znaki diakrytyczne to najłatwiejszy
# sposób, żeby te dwie implementacje dały różny wynik.
_DEMO_DISPLAY_NAME = "Demo User"

# Adres filii — jeden na filię. W Raczyńskich `secondarylocationname` wypożyczenia to adres filii (REQ-L3),
# a `search_data` używa tego samego adresu jako `subLocation` holdingu (od REQ-G6 rekord
# `pnxs/L/alma{mmsid}` pokazuje go przy wypożyczeniu), więc trzymamy go tu, w jednym miejscu.
BRANCH_ADDRESS: dict[str, str] = {
    "Filia Demo 1": "ul. Testowa 1",
    "Filia Demo 2": "ul. Próbna 2",
    "Filia Demo 3": "ul. Demowa 3",
}

_INSTITUTION_NAME = "Nieoficjalna Biblioteka OMNIS (Demo)"
_INSTITUTION_CODE = "MOCK"
_NETWORK_CODE = "MOCK_NETWORK"

# SPEC.md REQ-L3: `loanstatus` jak w Primo z `lang=pl`. „Prolongowano” pojawia się po udanym `renew_loans`
# (REQ-13) albo od początku, jeśli szablon ma `renewed_before`.
_STATUS_REGULAR = "Zwykłe"
_STATUS_RENEWED = "Prolongowano"

# Statyczne "szablony" wypożyczeń: *_offset_days są WZGLĘDEM date.today() w momencie odpowiedzi (SPEC.md:
# "nie hardkodować absolutnych dat") — jedyny mutowalny stan to _renewal_extensions.
#
# `title` to krótki tytuł dzieła, z którego `search_data` buduje katalog (testy wyszukiwarki na nim
# polegają). `loan_title` to tytuł, jaki zwraca `myaccount/loans` — w Primo z oznaczeniem odpowiedzialności
# po " / " (REQ-L3); jeden celowo bez " / ", żeby klient miał przypadek bez obcinania.
_LOAN_TEMPLATES: list[dict[str, Any]] = [
    {
        "loanid": "loan-001",
        "mmsid": "mock-mms-001",
        "title": "Pan Tadeusz",
        "loan_title": (
            "Pan Tadeusz, czyli Ostatni zajazd na Litwie : historia szlachecka z roku 1811 i 1812"
            " we dwunastu księgach wierszem / Adam Mickiewicz."
        ),
        "author": "Adam Mickiewicz",
        "due_offset_days": 5,
        "loan_offset_days": -25,
        # REQ-L5: dwie prolongaty po +14 dni mieszczą się dokładnie w limicie. tests/test_contract.py
        # prolonguje to wypożyczenie (pierwsze z renew="Y"), więc limit musi zostawić miejsce na >= 1.
        "maxrenew_offset_days": 33,
        "mainlocationname": "Filia Demo 1",
        "secondarylocationname": BRANCH_ADDRESS["Filia Demo 1"],
        "itembarcode": "DEMO0001",
        "callnumber2": "821.162.1-13",
        "renew": "Y",
        "renewstatus": [],
    },
    {
        "loanid": "loan-002",
        "mmsid": "mock-mms-002",
        "title": "Lalka",
        "loan_title": "Lalka / Bolesław Prus.",
        "author": "Bolesław Prus",
        "due_offset_days": -3,  # przeterminowane — SPEC.md "Dane demo" wymaga >=1 takiego
        "loan_offset_days": -33,
        "maxrenew_offset_days": 25,
        "mainlocationname": "Filia Demo 2",
        "secondarylocationname": BRANCH_ADDRESS["Filia Demo 2"],
        "itembarcode": "DEMO0002",
        "callnumber2": "F.821.162.1-3",
        "renew": "Y",
        "renewstatus": [],
    },
    {
        "loanid": "loan-003",
        "mmsid": "mock-mms-003",
        "title": "Quo Vadis",
        "loan_title": "Quo vadis : powieść z czasów Nerona / Henryk Sienkiewicz.",
        "author": "Henryk Sienkiewicz",
        "due_offset_days": 20,
        "loan_offset_days": -10,
        "maxrenew_offset_days": 48,
        "mainlocationname": "Filia Demo 1",
        # REQ-L3: jedno wypożyczenie bez adresu filii, żeby klient miał też przypadek `null`.
        "secondarylocationname": None,
        "itembarcode": "DEMO0003",
        "callnumber2": "821.162.1-3",
        "renew": "N",  # nie-odnawialne — SPEC.md "Dane demo" wymaga >=1 takiego
        # REQ-L2: tekst widziany na żywo w Raczyńskich (termin zwrotu za > 7 dni).
        "renewstatus": ["Okres, na który można dokonać prolongaty to 7 dni przed datą zwrotu"],
    },
    {
        "loanid": "loan-004",
        "mmsid": "mock-mms-004",
        "title": "Dziady",
        "loan_title": "Dziady",
        "author": "Adam Mickiewicz",
        "due_offset_days": 1,
        "loan_offset_days": -29,
        "maxrenew_offset_days": 1,
        "mainlocationname": "Filia Demo 3",
        "secondarylocationname": BRANCH_ADDRESS["Filia Demo 3"],
        "itembarcode": "DEMO0004",
        "callnumber2": "821.162.1-2",
        "renew": "N",
        "renewed_before": True,
        # REQ-L2: drugi powód, przykładowy (niewidziany na żywo), i jako goły string zamiast listy — Primo
        # potrafi tak zwijać jednoelementowe tablice (test odporności klienta).
        "renewstatus": "Osiągnięto limit prolongat",
    },
]

# SPEC.md REQ-L4: zakończone wypożyczenia dla `type=history` — statyczne, niezależne od aktywnych, daty w
# przeszłości względem dziś. `mmsid` to edycje z katalogu (`search_data._EDITIONS_A/B/C`), więc rekord
# `pnxs/L/alma{mmsid}` istnieje także dla pozycji z historii.
_HISTORY_TEMPLATES: list[dict[str, Any]] = [
    {
        "loanid": "hist-001",
        "mmsid": "MOCK-SEARCH-A1",
        "loan_title": "Cienie Nibylandii / Karolina Nibylska.",
        "author": "Karolina Nibylska",
        "year": "2022",
        "loan_offset_days": -70,
        "due_offset_days": -40,
        "return_offset_days": -45,
        "returnhour": "1749",
        "loanstatus": _STATUS_REGULAR,
        "mainlocationname": "Filia Demo 1",
        "secondarylocationname": BRANCH_ADDRESS["Filia Demo 1"],
        "itembarcode": "DEMO0101",
        "callnumber2": "821.162.1-3",
        "itemcategorycode": "WZ_30",
        "itemcategoryname": "Wypożyczane na 30 dni",
        "itemstatusname": "Wypożyczenie",
    },
    {
        "loanid": "hist-002",
        "mmsid": "MOCK-SEARCH-B1",
        "loan_title": "Ostatni rejs wyobraźni / Marek Zmyślak.",
        "author": "Marek Zmyślak",
        "year": "2019",
        "loan_offset_days": -120,
        "due_offset_days": -76,
        "return_offset_days": -77,
        "returnhour": "1012",
        "loanstatus": _STATUS_RENEWED,
        "mainlocationname": "Filia Demo 3",
        "secondarylocationname": BRANCH_ADDRESS["Filia Demo 3"],
        "itembarcode": "DEMO0102",
        "callnumber2": "821.162.1-3",
        "itemcategorycode": "WZ_30",
        "itemcategoryname": "Wypożyczane na 30 dni",
        "itemstatusname": "Wypożyczenie",
    },
    {
        "loanid": "hist-003",
        "mmsid": "MOCK-SEARCH-C1",
        "loan_title": "Biblioteka za mgłą : opowiadania / Alicja Wyobraźnicka.",
        "author": "Alicja Wyobraźnicka",
        "year": "2021",
        "loan_offset_days": -200,
        "due_offset_days": -170,
        "return_offset_days": -171,
        "returnhour": "1530",
        "loanstatus": _STATUS_REGULAR,
        "mainlocationname": "Filia Demo 1",
        # REQ-L4: egzemplarz wycofany po zwrocie — w Primo inna "lokalizacja drugorzędna" niż adres filii.
        "secondarylocationname": "Księga ubytków FD1",
        "itembarcode": "DEMO0103",
        "callnumber2": "821.162.1-32",
        "itemcategorycode": "UBYT",
        "itemcategoryname": "Ubytkowany",
        "itemstatusname": "W procesie",
    },
    {
        "loanid": "hist-004",
        "mmsid": "MOCK-SEARCH-A2",
        "loan_title": "Cienie Nibylandii",
        "author": "Karolina Nibylska",
        "year": "2015",
        "loan_offset_days": -300,
        "due_offset_days": -256,
        "return_offset_days": -260,
        "returnhour": "0915",
        "loanstatus": _STATUS_RENEWED,
        "mainlocationname": "Filia Demo 2",
        "secondarylocationname": None,
        "itembarcode": "DEMO0104",
        "callnumber2": "821.162.1-3",
        "itemcategorycode": "WZ_30",
        "itemcategoryname": "Wypożyczane na 30 dni",
        "itemstatusname": "Wypożyczenie",
    },
]

# Rok wydania egzemplarzy wypożyczeń — ten sam co `date` edycji w `search_data._works_from_loans()`.
LOAN_EDITION_YEAR = "2000"

# loan_id -> dodatkowe dni doliczone przez renew_demo_loan(); resetowane przez reset_state().
_renewal_extensions: dict[str, int] = {}


# --- Zamówienia (SPEC.md REQ-H1..REQ-H3, REQ-H6) -------------------------------------------------------------
# Stan modułowy, w pamięci procesu (REQ-H1): konto demo jest publiczne i współdzielone, więc zamówienie
# złożone przez jednego klienta widzi każdy. Leniwa inicjalizacja (`_holds is None`), bo tytuł seeda
# pochodzi z katalogu (`search_data`), który importuje ten moduł — import wprost byłby cykliczny.

MAX_ACTIVE_HOLDS = 5  # REQ-H2: twardy limit aktywnych zamówień (razem z seedem)
HOLD_TTL = timedelta(hours=24)  # REQ-H2: TTL zamówień złożonych przez użytkownika (seed bez TTL)
_SEED_READY_DAYS = 7  # REQ-H5: „Na półce rezerwacji do” = dziś + 7 dni
_STATUS_IN_PROGRESS = "W realizacji"

_SEED_MMSID = "MOCK-SEARCH-B1"  # edycja z katalogu, nie z wypożyczeń (REQ-H3)

_clock: Callable[[], datetime] = datetime.now
_holds: Optional[list[dict[str, Any]]] = None
_hold_counter = itertools.count(1)


def set_clock(clock: Optional[Callable[[], datetime]]) -> None:
    """Wstrzykiwalny zegar dla TTL zamówień (testy bez `sleep`); `None` przywraca `datetime.now`."""
    global _clock
    _clock = clock or datetime.now


def _next_request_id() -> str:
    return f"MOCK-REQ-{next(_hold_counter):04d}"


def _init_holds() -> list[dict[str, Any]]:
    """Fixture startowy (REQ-H3): jedno zamówienie „gotowe do odbioru”, fikcyjny tytuł z katalogu."""
    from omnis_mock import search_data  # lokalnie: search_data importuje data (cykl)

    info = search_data.catalog_hold_info(_SEED_MMSID)
    assert info is not None
    return [
        {
            "requestid": _next_request_id(),
            "mmsid": info["mmsid"],
            "item_id": info["item_id"],
            "title": info["title"],
            "author": info["author"],
            "pickup_name": info["pickups"][0]["name"],
            "created": _clock(),
            "seed": True,
        }
    ]


def _active_holds() -> list[dict[str, Any]]:
    """Aktualna lista zamówień po usunięciu przeterminowanych (REQ-H2: TTL liczony od złożenia, przy
    najbliższym odczycie). Seed nie podlega TTL."""
    global _holds
    if _holds is None:
        _holds = _init_holds()
    now = _clock()
    _holds[:] = [h for h in _holds if h["seed"] or now - h["created"] < HOLD_TTL]
    return _holds


def place_demo_hold(mmsid: str, item_id: str, title: str, author: str, pickup_name: str) -> str:
    """REQ-H10b: dodaje zamówienie („W realizacji”), zwraca nowy `requestid`. Po przekroczeniu limitu
    (REQ-H2) usuwa najstarsze zamówienia złożone przez użytkownika; seed zostaje."""
    holds = _active_holds()
    request_id = _next_request_id()
    holds.append(
        {
            "requestid": request_id,
            "mmsid": mmsid,
            "item_id": item_id,
            "title": title,
            "author": author,
            "pickup_name": pickup_name,
            "created": _clock(),
            "seed": False,
        }
    )
    while len(holds) > MAX_ACTIVE_HOLDS:
        oldest = min((h for h in holds if not h["seed"]), key=lambda h: h["created"], default=None)
        if oldest is None:
            break
        holds.remove(oldest)
    return request_id


def cancel_demo_hold(request_id: str) -> bool:
    """REQ-H11: usuwa zamówienie (seed także). Nieznany id -> False (no-op)."""
    holds = _active_holds()
    for hold in holds:
        if hold["requestid"] == request_id:
            holds.remove(hold)
            return True
    return False


def hold_queue_length(item_id: str) -> int:
    """REQ-H12: liczba aktywnych zamówień na egzemplarz."""
    return sum(1 for h in _active_holds() if h["item_id"] == item_id)


def get_demo_holds() -> list[dict[str, str]]:
    """`data.holds.hold` dla `GET /myaccount/requests` (REQ-H5): same stringi, `available`/`cancel` jako
    `"Y"`/`"N"` (nie bool). Seed jest od razu na półce (`available: "Y"`), reszta „W realizacji”."""
    now = _clock()
    result = []
    for hold in _active_holds():
        if hold["seed"]:
            ready_until = (now.date() + timedelta(days=_SEED_READY_DAYS)).strftime("%d/%m/%Y")
            status, available = f"Na półce rezerwacji do {ready_until}", "Y"
        else:
            status, available = _STATUS_IN_PROGRESS, "N"
        result.append(
            {
                "requestid": hold["requestid"],
                "title": hold["title"],
                "author": hold["author"],
                "holdstatus": status,
                "available": available,
                "cancel": "Y",
                "pickuplocationname": hold["pickup_name"],
                # Seed liczony od dziś, żeby się nie starzał (REQ-H2/H3); reszta od czasu złożenia.
                "requestdate": _format_date((now if hold["seed"] else hold["created"]).date()),
                "mmsid": hold["mmsid"],
                "ilsinstitutionname": _INSTITUTION_NAME,
                "ilsinstitutioncode": _INSTITUTION_CODE,
            }
        )
    return result


def _format_date(value: date) -> str:
    return value.strftime("%Y%m%d")


def location_code(main_location: str) -> str:
    """ "Filia Demo 1" -> "FD1" — ten sam kod co `holding.libraryCode` w katalogu (`search_data`)."""
    number = main_location.rsplit(" ", 1)[-1]
    return f"FD{number}"


def _item_fields(loanid: str, mmsid: str, main_location: str) -> dict[str, str]:
    """Klucze REQ-L1 wspólne dla aktywnych i historii. Identyfikatory celowo "mockowe" (nie w formacie
    prawdziwych mmsid/itemid Alma), kody lokalizacji spójne z holdingiem tego rekordu w katalogu."""
    code = location_code(main_location)
    return {
        "itemid": f"MOCK-ITEM-{loanid.upper()}",
        "mainlocationcode": code,
        "secondarylocationcode": f"{code}dz",
        "ilsinstitutioncode": _INSTITUTION_CODE,
        "nzmmsid": f"MOCK-NZ-{mmsid.upper()}",
        "nzilsinstitutioncode": _NETWORK_CODE,
    }


def get_demo_counters() -> list[dict[str, str]]:
    """`data.listofactions.action` dla `GET /myaccount/counters` (SPEC.md REQ-6/REQ-7).

    `Fines` w formacie Z KROPKĄ ("0.00") — REQ-7, inny format niż w /fines (poza zakresem Layer 1).
    Liczy tylko aktywne wypożyczenia, nie historię (REQ-L4).
    """
    loans = get_demo_loans()
    return [
        {"type": "Loans", "value": str(len(loans))},
        {"type": "Requests", "value": str(len(_active_holds()))},  # REQ-H6
        {"type": "Fines", "value": "0.00"},
    ]


def get_demo_loans() -> list[dict[str, Any]]:
    """Aktualna lista wypożyczeń (SPEC.md REQ-9, REQ-10, REQ-11, REQ-L1..L3) — daty liczone na bieżąco
    względem dziś, z uwzględnieniem ewentualnych prolongat (`_renewal_extensions`).
    """
    today = date.today()
    result = []
    for tmpl in _LOAN_TEMPLATES:
        extension_days = _renewal_extensions.get(tmpl["loanid"], 0)
        due_date = today + timedelta(days=tmpl["due_offset_days"] + extension_days)
        loan_date = today + timedelta(days=tmpl["loan_offset_days"])
        max_renew_date = today + timedelta(days=tmpl["maxrenew_offset_days"])
        renewed = extension_days > 0 or tmpl.get("renewed_before", False)
        result.append(
            {
                "loanid": tmpl["loanid"],
                "mmsid": tmpl["mmsid"],
                "title": tmpl["loan_title"],
                "author": tmpl["author"],
                "duedate": _format_date(due_date),
                # REQ-L3: Primo zwraca godzinę bez dwukropka.
                "duehour": "2359",
                "loandate": _format_date(loan_date),
                "loanstatus": _STATUS_RENEWED if renewed else _STATUS_REGULAR,
                "ilsinstitutionname": _INSTITUTION_NAME,
                "mainlocationname": tmpl["mainlocationname"],
                "secondarylocationname": tmpl["secondarylocationname"],
                "itembarcode": tmpl["itembarcode"],
                "renew": tmpl["renew"],
                "callnumber2": tmpl["callnumber2"],
                # REQ-L1: z kropką na końcu, jak w Primo.
                "year": f"{LOAN_EDITION_YEAR}.",
                "itemcategorycode": "WZ_30",
                "itemcategoryname": "Wypożyczane na 30 dni",
                "itemstatusname": "Wypożyczenie",
                "maxrenewdate": _format_date(max_renew_date),
                "renewstatuses": {"renewstatus": tmpl["renewstatus"]},
                "alerts": [],
                **_item_fields(tmpl["loanid"], tmpl["mmsid"], tmpl["mainlocationname"]),
            }
        )
    return result


def get_demo_history() -> list[dict[str, Any]]:
    """Zakończone wypożyczenia dla `type=history` (SPEC.md REQ-L4): klucze REQ-10 i REQ-L1, dodatkowo
    `returndate`/`returnhour`, bez `renewstatuses`/`maxrenewdate`/`alerts`, zawsze `renew: "N"`."""
    today = date.today()
    return [
        {
            "loanid": tmpl["loanid"],
            "mmsid": tmpl["mmsid"],
            "title": tmpl["loan_title"],
            "author": tmpl["author"],
            "duedate": _format_date(today + timedelta(days=tmpl["due_offset_days"])),
            "duehour": "2359",
            "loandate": _format_date(today + timedelta(days=tmpl["loan_offset_days"])),
            "loanstatus": tmpl["loanstatus"],
            "ilsinstitutionname": _INSTITUTION_NAME,
            "mainlocationname": tmpl["mainlocationname"],
            "secondarylocationname": tmpl["secondarylocationname"],
            "itembarcode": tmpl["itembarcode"],
            "renew": "N",
            "callnumber2": tmpl["callnumber2"],
            "year": f"{tmpl['year']}.",
            "itemcategorycode": tmpl["itemcategorycode"],
            "itemcategoryname": tmpl["itemcategoryname"],
            "itemstatusname": tmpl["itemstatusname"],
            "returndate": _format_date(today + timedelta(days=tmpl["return_offset_days"])),
            "returnhour": tmpl["returnhour"],
            **_item_fields(tmpl["loanid"], tmpl["mmsid"], tmpl["mainlocationname"]),
        }
        for tmpl in _HISTORY_TEMPLATES
    ]


def renew_demo_loan(loan_id: str) -> bool:
    """SPEC.md REQ-13/REQ-13b/REQ-L5: odnawialny `loan_id` -> +14 dni do terminu, zwraca True. No-op
    (False, i tak `200` w main.py) dla nieznanego id, dla `renew: "N"` i gdy nowy termin przekroczyłby
    `maxrenewdate`."""
    tmpl = next((t for t in _LOAN_TEMPLATES if t["loanid"] == loan_id), None)
    if tmpl is None or tmpl["renew"] != "Y":
        return False
    extension_days = _renewal_extensions.get(loan_id, 0) + 14
    if tmpl["due_offset_days"] + extension_days > tmpl["maxrenew_offset_days"]:
        return False
    _renewal_extensions[loan_id] = extension_days
    return True


def reset_state() -> None:
    """Resetuje prolongaty i zamówienia (z powrotem do seeda) oraz zegar (używane przez testy)."""
    global _holds, _hold_counter
    _renewal_extensions.clear()
    _holds = None
    _hold_counter = itertools.count(1)
    set_clock(None)


def check_credentials(username: str, password: str) -> Optional[dict[str, str]]:
    """SPEC.md REQ-1/REQ-3/REQ-4: zwraca dane do JWT jeśli to demo-konto, inaczej None (-> 401 w main.py)."""
    if username == DEMO_USERNAME and password == DEMO_PASSWORD:
        return {"displayName": _DEMO_DISPLAY_NAME, "userName": DEMO_USERNAME}
    return None
