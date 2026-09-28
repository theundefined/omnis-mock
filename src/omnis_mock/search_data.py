"""Fixture katalogu (Layer 2 — wyszukiwarka). Kontrakt: docs/SPEC.md REQ-15..REQ-18b, pełna lista pól
i uzasadnienie włączenia/wykluczenia: docs/API_FIELDS.md.

3 fikcyjne dzieła (tytuły/autorzy jawnie zmyśleni — publiczny mock, nie przypisujemy fałszywej
dostępności możliwej do zidentyfikowania osobie) + 4 dzieła wygenerowane z `data._LOAN_TEMPLATES`
(zobacz `_works_from_loans()` niżej) — bez tych ostatnich wyszukiwarka i konto demo pokazywałyby dwa
rozłączne zbiory książek: tytuł wypożyczony na koncie demo nigdy nie dałoby się znaleźć w katalogu, co
wygląda jak błąd przy ręcznym testowaniu. Kształt `pnx`/`holding` odzwierciedla REALNE odpowiedzi
Primo (zweryfikowane względem `omnis-py/debug_search_output/*.json` i
`omnis-mobile/docs/api-verification-response.md`), nie tylko minimalny zestaw pól czytany przez jednego
klienta — patrz docs/API_FIELDS.md dla pełnej tabeli pole-po-polu.

Bez stanu mutowalnego — w przeciwieństwie do `data.py` (wypożyczenia), katalog się nie zmienia w runtime;
`_works_from_loans()` czyta tylko statyczny `data._LOAN_TEMPLATES`, nigdy `data.get_demo_loans()` ani
`data.renew_demo_loan()`, więc prolongata wypożyczenia nie zmienia terminu widocznego w wyszukiwarce.
"""

from datetime import date, timedelta
from typing import Any, Optional

from omnis_mock import data

# Institution/organization code używany w fixture — zgodny z demo institution z docs/SPEC.md ("MOCK").
_INSTITUTION = "MOCK"

_EDITIONS_A: list[dict[str, Any]] = [
    {
        "mmsid": "MOCK-SEARCH-A1",
        "edition_label": "Wydanie II poprawione",
        "date": "2022",
        "isbn": "9788300000011",
        "format_display": "312 stron : ilustracje ; 21 cm.",
        "holding": {
            "main_location": "Filia Demo 1",
            "library_code": "FD1",
            "sub_location": "ul. Testowa 1",
            "sub_location_code": "FD1dz",
            "availability_status": "available",
            "hold_id": "MOCK-HOLD-A1",
            "stack_map_url": "https://maps.app.goo.gl/mockA1",
        },
        "due_offset_days": None,
    },
    {
        "mmsid": "MOCK-SEARCH-A2",
        "edition_label": "Wydanie I",
        "date": "2015",
        "isbn": "9788300000004",
        "format_display": "298 stron ; 20 cm.",
        "holding": {
            "main_location": "Filia Demo 2",
            "library_code": "FD2",
            "sub_location": "ul. Próbna 2",
            "sub_location_code": "FD2dz",
            "availability_status": "unavailable",
            "hold_id": "MOCK-HOLD-A2",
            "stack_map_url": "https://maps.app.goo.gl/mockA2",
        },
        # Przeterminowane (data w przeszłości) -> itemstatusname zawiera "przekroczon" -> overdue=True.
        "due_offset_days": -5,
    },
]

_EDITIONS_B: list[dict[str, Any]] = [
    {
        "mmsid": "MOCK-SEARCH-B1",
        "edition_label": "Wydanie I",
        "date": "2019",
        "isbn": "9788300000028",
        "format_display": "204 strony ; 21 cm.",
        "holding": {
            "main_location": "Filia Demo 3",
            "library_code": "FD3",
            "sub_location": "ul. Demowa 3",
            "sub_location_code": "FD3dz",
            "availability_status": "available",
            "hold_id": "MOCK-HOLD-B1",
            "stack_map_url": "https://maps.app.goo.gl/mockB1",
        },
        # Dostępne -> klient nigdy nie woła getPhysicalService/ILSServices dla tej gałęzi.
        "due_offset_days": None,
    },
]

_EDITIONS_C: list[dict[str, Any]] = [
    {
        "mmsid": "MOCK-SEARCH-C1",
        "edition_label": "Wydanie I",
        "date": "2021",
        "isbn": "9788300000035",
        "format_display": "176 stron : ilustracje ; 22 cm.",
        "holding": {
            "main_location": "Filia Demo 1",
            "library_code": "FD1",
            "sub_location": "ul. Testowa 1",
            "sub_location_code": "FD1dz",
            "availability_status": "unavailable",
            "hold_id": "MOCK-HOLD-C1",
            "stack_map_url": "https://maps.app.goo.gl/mockC1",
        },
        # Data w przyszłości -> itemstatusname bez "przekroczon" -> overdue=False.
        "due_offset_days": 12,
    },
]


# SPEC.md REQ-G6: seria (`addata.seriestitle`) dla dzieł z wypożyczeń demo, w prawdziwym formacie Primo —
# dwa tomy tej samej serii z RÓŻNYM zapisem tomu/odpowiedzialności (omnis-mobile tnie nazwę serii na
# pierwszym `;` i ` / `, a numer tomu bierze z pierwszej liczby po `;`). Oba to wypożyczenia konta demo, więc
# "Seria: …" przy wypożyczeniu (omnis-mobile v0.6.2, rekord z `pnxs/L/alma{mmsid}`) prowadzi do obu tomów.
# Pozostałe wypożyczenia celowo bez serii.
_LOAN_SERIES: dict[str, str] = {
    "loan-001": "Dzieła wszystkie / Adam Mickiewicz ; [t. 4]",
    "loan-004": "Dzieła wszystkie ;  3",
}


def _works_from_loans() -> list[dict[str, Any]]:
    """Generuje wpisy katalogu wprost z `data._LOAN_TEMPLATES` (statyczny szablon, NIE
    `data.get_demo_loans()`/`data.renew_demo_loan()` — patrz docstring modułu), po jednym dziele/edycji na
    wypożyczenie, z tym samym `mmsid` co odpowiadający loan. Każde jest oznaczone jako `unavailable` z
    `due_offset_days` identycznym jak termin zwrotu tego wypożyczenia — inaczej książka widoczna jako
    wypożyczona na koncie demo byłaby niewyszukiwalna w katalogu (dokładnie zgłoszona niespójność).
    """
    works = []
    for tmpl in data._LOAN_TEMPLATES:
        library_code = data.location_code(tmpl["mainlocationname"])
        works.append(
            {
                "frbrgroupid": f"MOCK-GROUP-{tmpl['loanid'].upper()}",
                "title": tmpl["title"],
                "author": tmpl["author"],
                "genres": ["Literatura polska", "Klasyka"],
                "subjects": ["Historia", "Obyczaje"],
                "series": _LOAN_SERIES.get(tmpl["loanid"]),
                "language": "pol",
                "publisher": "Wydawnictwo Demo",
                "place": "Warszawa",
                "editions": [
                    {
                        "mmsid": tmpl["mmsid"],
                        "edition_label": "Wydanie biblioteczne",
                        "date": data.LOAN_EDITION_YEAR,
                        "isbn": f"9788300{tmpl['loanid'][-3:]}0000",
                        "format_display": "320 stron ; 21 cm.",
                        "holding": {
                            "main_location": tmpl["mainlocationname"],
                            "library_code": library_code,
                            # Adres filii jak `secondarylocationname` wypożyczeń (REQ-L3) — jedno źródło w `data.py`.
                            "sub_location": data.BRANCH_ADDRESS[tmpl["mainlocationname"]],
                            "sub_location_code": f"{library_code}dz",
                            "availability_status": "unavailable",
                            "hold_id": f"MOCK-HOLD-{tmpl['loanid'].upper()}",
                            "stack_map_url": f"https://maps.app.goo.gl/mock{tmpl['loanid'].upper()}",
                        },
                        # Ten sam termin co `due_offset_days` w `_LOAN_TEMPLATES` — patrz docstring funkcji.
                        "due_offset_days": tmpl["due_offset_days"],
                    }
                ],
            }
        )
    return works


_WORKS: list[dict[str, Any]] = [
    {
        "frbrgroupid": "MOCK-GROUP-A",
        "title": "Cienie Nibylandii",
        "author": "Karolina Nibylska",
        "genres": ["Fantastyka", "Powieść"],
        "subjects": ["Magia", "Przyjaźń", "Podróże"],
        "series": "Kroniki Nibylandii / Karolina Nibylska ; 1",
        "language": "pol",
        "publisher": "Wydawnictwo Mgławica",
        "place": "Poznań",
        "editions": _EDITIONS_A,
    },
    {
        "frbrgroupid": "MOCK-GROUP-B",
        "title": "Ostatni Rejs Wyobraźni",
        "author": "Marek Zmyślak",
        "genres": ["Przygodowa"],
        "subjects": ["Morze", "Odkrycia"],
        "series": None,
        "language": "pol",
        "publisher": "Wydawnictwo Kompas",
        "place": "Kraków",
        "editions": _EDITIONS_B,
    },
    {
        "frbrgroupid": "MOCK-GROUP-C",
        "title": "Biblioteka Za Mgłą",
        "author": "Alicja Wyobraźnicka",
        "genres": ["Fantastyka", "Opowiadania"],
        "subjects": ["Biblioteki", "Tajemnica"],
        "series": None,
        "language": "pol",
        "publisher": "Wydawnictwo Mgławica",
        "place": "Poznań",
        "editions": _EDITIONS_C,
    },
    *_works_from_loans(),
]

_MMSID_TO_WORK_EDITION: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {
    edition["mmsid"]: (work, edition) for work in _WORKS for edition in work["editions"]
}


def _alma_id(mmsid: str) -> str:
    return f"alma{mmsid}"


def _inverted_author(author: str) -> str:
    """ "Karolina Nibylska" -> "Nibylska, Karolina" — format, w jakim prawdziwe Primo zwraca autora w
    `addata.au`/`addau`/`sort.author`/`display.contributor` (np. "Weir, Andy", "Mickiewicz, Adam"). Fixture
    trzyma autora w naturalnej kolejności (tak też jest w `display.title` i w wypożyczeniach, `data.py`)."""
    first, _, last = author.rpartition(" ")
    return f"{last}, {first}" if first else author


def _build_pnx(work: dict[str, Any], edition: dict[str, Any]) -> dict[str, Any]:
    """Kształt `pnx` z realnym zestawem pól (docs/API_FIELDS.md) — nie tylko te czytane przez `omnis-py`,
    żeby ten sam fixture obsłużył też pola specyficzne dla `omnis-mobile` i każdą przyszłą zmianę klienta.
    """
    mmsid = edition["mmsid"]
    recordid = _alma_id(mmsid)
    title = work["title"]
    author = work["author"]
    author_inv = _inverted_author(author)
    series = work["series"]

    return {
        "display": {
            "source": ["Alma (Mock)"],
            "type": ["book"],
            "language": [work["language"]],
            "title": [f"{title} / {author}."],
            "format": [edition["format_display"]],
            "identifier": [f"$$CISBN$$V{edition['isbn']}"],
            "creationdate": [edition["date"]],
            "publisher": [f"{work['place']} : {work['publisher']}"],
            "mms": [mmsid],
            "contributor": [f"{author_inv} Autor$$Q{author_inv}"],
            "edition": [edition["edition_label"]],
            "series": [f"{series}$$Q{series}"] if series else [],
            "genre": list(work["genres"]),
            "place": [f"{work['place']} :"],
            "version": ["1"],
            "subject": list(work["subjects"]),
        },
        "addata": {
            "au": [author_inv],
            "aulast": [author.split(" ")[-1]],
            "aufirst": [author.split(" ")[0]],
            "auinit": [author[0]],
            "addau": [author_inv],
            "date": [edition["date"]],
            "isbn": [edition["isbn"]],
            "cop": [work["place"]],
            "pub": [work["publisher"]],
            "edition": [edition["edition_label"]],
            "seriestitle": [series] if series else [],
            "format": ["book"],
            "genre": ["book"],
            "ristype": ["BOOK"],
            "btitle": [title],
        },
        "sort": {
            "title": [f"{title} /"],
            "author": [author_inv],
            "creationdate": [edition["date"]],
        },
        "control": {
            "sourcerecordid": [mmsid],
            "recordid": [recordid],
            "sourceid": "alma",
            "originalsourceid": [f"MOCK-ORIG-{mmsid}"],
            "sourcesystem": ["OTHER"],
            "sourceformat": ["MARC21"],
            "score": ["1.0000000"],
            "isDedup": False,
        },
        "facets": {
            "frbrtype": ["6"],
            "frbrgroupid": [work["frbrgroupid"]],
        },
    }


def _build_holding(edition: dict[str, Any]) -> dict[str, Any]:
    """Pełny (23-polowy) `holding`, jak realne `delivery.holding[]` (docs/API_FIELDS.md). Wartości bez
    znaczenia funkcjonalnego dla żadnego znanego klienta są stałymi, realistycznymi placeholderami.

    `holKey` jest jedynym z tych "dekoracyjnych" pól, które JEST funkcjonalnie wymagane przez realny
    `ILSServices/holdings` (REQ-18b) — `omnis-py` przekazuje cały ten dict 1:1 z powrotem w kolejnym
    żądaniu, więc obecność `holKey` tutaj jest tym, co sprawia, że termin zwrotu w ogóle się rozwiązuje.
    """
    h = edition["holding"]
    mmsid = edition["mmsid"]
    return {
        "isValidUser": True,
        "organization": _INSTITUTION,
        "libraryCode": h["library_code"],
        "availabilityStatus": h["availability_status"],
        "subLocation": h["sub_location"],
        "subLocationCode": h["sub_location_code"],
        "mainLocation": h["main_location"],
        "callNumber": "",
        "callNumberType": "8",
        "holdingURL": "OVP",
        "adaptorid": "ALMA_01",
        "ilsApiId": mmsid,
        "holdId": h["hold_id"],
        "holKey": f"HoldingResultKey [mid={h['hold_id']}, libraryId=MOCK-LIB-{h['library_code']}, "
        f"locationCode={h['sub_location_code']}, callNumber=null]",
        "matchForHoldings": [{"matchOn": "MainLocation", "holdingRecord": "852##b"}],
        "stackMapUrl": h["stack_map_url"],
        "relatedTitle": None,
        "translateRelatedTitle": None,
        "yearFilter": None,
        "volumeFilter": None,
        "singleUnavailableItemProcessType": None,
        "boundWith": False,
        "@id": f"_:{mmsid}",
    }


def _parse_q(q: str) -> tuple[str, str]:
    """`"<pole>,<operator>,<wartość>"` -> `(pole, wartość)` (SPEC.md REQ-G5). Dzieli TYLKO na dwóch pierwszych
    przecinkach — wartość może zawierać przecinki (`"creator,contains,Weir, Andy"`). Operator jest
    ignorowany (każdy traktowany jak `contains`). `q` bez tego formatu -> `("any", q)`."""
    parts = q.split(",", 2)
    if len(parts) == 3:
        return parts[0], parts[2]
    return "any", q


def _normalize(text: str) -> str:
    """Case-insensitive, przecinki jako spacje, zwinięte białe znaki — żeby `"Nibylska, Karolina"` i
    `"Nibylska Karolina"` dopasowały się tak samo (prawdziwe Primo zwraca dla obu te same wyniki, REQ-G5)."""
    return " ".join(text.replace(",", " ").lower().split())


def _haystack(work: dict[str, Any], field: str) -> str:
    """Tekst, względem którego dopasowujemy zapytanie. `creator` — TYLKO autor (w obu formach: naturalnej i
    "Nazwisko, Imię"), bez tytułu (REQ-G5); `series` — TYLKO seria (REQ-G6); `any` i nieznane pola —
    tytuł + autor (REQ-15)."""
    author = work["author"]
    authors = f"{author} {_inverted_author(author)}"
    if field == "creator":
        return _normalize(authors)
    if field == "series":
        # REQ-G6: CAŁY `addata.seriestitle` (z tomem i odpowiedzialnością, jak w prawdziwym Primo —
        # tam `series,contains,Rowling` trafia "Harry Potter / J. K. Rowling ; 2"), nie tytuł/autor.
        return _normalize(work["series"] or "")
    return _normalize(f"{work['title']} {authors}")


def _parse_qinclude(q_include: str) -> Optional[str]:
    prefix = "facet_frbrgroupid,exact,"
    return q_include[len(prefix) :] if q_include.startswith(prefix) else None


def search(q: str, q_include: str, offset: int, limit: int) -> tuple[list[dict[str, Any]], int]:
    """SPEC.md REQ-15/REQ-16: top-level search (`q`, paginowane `offset`/`limit`) albo group expansion
    (`qInclude`, zwraca wszystkie edycje danej grupy, bez paginacji — jak realne Primo dla tego trybu).

    Dopasowanie top-level: case-insensitive substring CAŁEGO zapytania względem "{title} {author}" —
    świadomie NIE tokenizacja/OR (REQ-15), żeby ogólne słowo nie trafiło przypadkiem w jeden z 3
    fikcyjnych rekordów i nie zepsuło REQ-14 (`search_books("cokolwiek")` musi zostać pusty). Pole z `q`
    (REQ-G5): `creator` zawęża dopasowanie do samego autora, `any` i każde inne — tytuł + autor.
    """
    group_id = _parse_qinclude(q_include) if q_include else None
    if group_id:
        editions = sorted(
            ((work, edition) for work in _WORKS if work["frbrgroupid"] == group_id for edition in work["editions"]),
            key=lambda pair: pair[1]["date"],
            reverse=True,
        )
        docs = [{"pnx": _build_pnx(work, edition)} for work, edition in editions]
        return docs, len(docs)

    field, value = _parse_q(q)
    query_text = _normalize(value)
    if not query_text:
        return [], 0

    matched_works = [work for work in _WORKS if query_text in _haystack(work, field)]
    total = len(matched_works)
    page = matched_works[offset : offset + limit]
    docs = [{"pnx": _build_pnx(work, work["editions"][0])} for work in page]
    return docs, total


def delivery(alma_ids: list[str]) -> list[dict[str, Any]]:
    """SPEC.md REQ-17: holding (pełny, z `holKey`) dla podanych alma-id spośród znanych edycji; nieznane
    id są pomijane. Nie waliduje, że `q`/`qInclude` w query params odpowiadają grupie tych id — patrz
    docs/API_FIELDS.md, "Świadome uproszczenia".
    """
    wanted = set(alma_ids)
    results = []
    for work in _WORKS:
        for edition in work["editions"]:
            recordid = _alma_id(edition["mmsid"])
            if recordid in wanted:
                results.append(
                    {
                        "pnx": {"control": {"recordid": [recordid]}},
                        "delivery": {"holding": [_build_holding(edition)]},
                    }
                )
    return results


def record(record_id: str) -> Optional[dict[str, Any]]:
    """SPEC.md REQ-G6: pełny rekord dla `GET /primaws/rest/pub/pnxs/L/{record_id}` — `pnx` (ten sam co w
    wynikach wyszukiwania, z `addata.au`/`seriestitle`) + `delivery.holding` (jak REQ-17). `record_id` to
    alma-id (`alma<mmsid>`); nieznany -> `None` (main.py zwraca wtedy pustą kopertę wyszukiwania, jak
    prawdziwe Primo)."""
    if not record_id.startswith("alma"):
        return None
    pair = _MMSID_TO_WORK_EDITION.get(record_id[len("alma") :])
    if pair is None:
        return None
    work, edition = pair
    return {"pnx": _build_pnx(work, edition), "delivery": {"holding": [_build_holding(edition)]}}


def physical_service_id(bare_mmsid: str) -> Optional[str]:
    """SPEC.md REQ-18: `f'PS-{bare_mmsid}'` dla znane edycje z ustawionym `due_offset_days` (czyli
    niedostępne), `None` inaczej -> `404` w main.py (klient łapie to jako `httpx.HTTPError` -> `None`,
    dokładnie oczekiwana ścieżka degradacji).
    """
    pair = _MMSID_TO_WORK_EDITION.get(bare_mmsid)
    if pair is None or pair[1]["due_offset_days"] is None:
        return None
    return f"PS-{bare_mmsid}"


def holding_status(physical_service_id_value: str, request_holding: Optional[dict[str, Any]]) -> Optional[str]:
    """SPEC.md REQ-18b (pułapka): `itemstatusname` z aktualną datą względną — TYLKO gdy
    `request_holding` zawiera niepusty `holKey`. Replikuje empirycznie zweryfikowane zachowanie realnego
    Primo (`omnis-mobile/docs/api-verification-response.md`): bez `holKey` w przychodzącym `locations[0]`
    endpoint zwraca puste dane mimo `200 OK`. Zwraca `None` w obu przypadkach degradacji (nieznany
    `physicalServiceId` ALBO brak `holKey`) — main.py mapuje `None` na pustą listę `items`, nie `404`.
    """
    if not physical_service_id_value.startswith("PS-"):
        return None
    bare_mmsid = physical_service_id_value[len("PS-") :]
    pair = _MMSID_TO_WORK_EDITION.get(bare_mmsid)
    if pair is None:
        return None
    due_offset_days = pair[1]["due_offset_days"]
    if due_offset_days is None:
        return None
    if not request_holding or not request_holding.get("holKey"):
        return None

    due_date = date.today() + timedelta(days=due_offset_days)
    date_str = due_date.strftime("%d/%m/%Y")
    if due_offset_days < 0:
        return f"Wypożyczony - termin zwrotu przekroczony od {date_str}"
    return f"Wypożyczenie do {date_str}"
