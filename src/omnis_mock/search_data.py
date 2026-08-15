"""Fixture katalogu (Layer 2 — wyszukiwarka). Kontrakt: docs/SPEC.md REQ-15..REQ-18b, pełna lista pól
i uzasadnienie włączenia/wykluczenia: docs/API_FIELDS.md.

3 fikcyjne dzieła (tytuły/autorzy jawnie zmyśleni — publiczny mock, nie przypisujemy fałszywej
dostępności możliwej do zidentyfikowania osobie). Kształt `pnx`/`holding` odzwierciedla REALNE odpowiedzi
Primo (zweryfikowane względem `omnis-py/debug_search_output/*.json` i
`omnis-mobile/docs/api-verification-response.md`), nie tylko minimalny zestaw pól czytany przez jednego
klienta — patrz docs/API_FIELDS.md dla pełnej tabeli pole-po-polu.

Bez stanu mutowalnego — w przeciwieństwie do `data.py` (wypożyczenia), katalog się nie zmienia w runtime.
"""

from datetime import date, timedelta
from typing import Any, Optional

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
]

_MMSID_TO_WORK_EDITION: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {
    edition["mmsid"]: (work, edition) for work in _WORKS for edition in work["editions"]
}


def _alma_id(mmsid: str) -> str:
    return f"alma{mmsid}"


def _build_pnx(work: dict[str, Any], edition: dict[str, Any]) -> dict[str, Any]:
    """Kształt `pnx` z realnym zestawem pól (docs/API_FIELDS.md) — nie tylko te czytane przez `omnis-py`,
    żeby ten sam fixture obsłużył też pola specyficzne dla `omnis-mobile` i każdą przyszłą zmianę klienta.
    """
    mmsid = edition["mmsid"]
    recordid = _alma_id(mmsid)
    title = work["title"]
    author = work["author"]
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
            "contributor": [f"{author} Autor$$Q{author}"],
            "edition": [edition["edition_label"]],
            "series": [f"{series}$$Q{series}"] if series else [],
            "genre": list(work["genres"]),
            "place": [f"{work['place']} :"],
            "version": ["1"],
            "subject": list(work["subjects"]),
        },
        "addata": {
            "au": [author],
            "aulast": [author.split(" ")[-1]],
            "aufirst": [author.split(" ")[0]],
            "auinit": [author[0]],
            "addau": [author],
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
            "author": [author],
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


def _parse_q(q: str) -> str:
    prefix = "any,contains,"
    return q[len(prefix) :] if q.startswith(prefix) else q


def _parse_qinclude(q_include: str) -> Optional[str]:
    prefix = "facet_frbrgroupid,exact,"
    return q_include[len(prefix) :] if q_include.startswith(prefix) else None


def search(q: str, q_include: str, offset: int, limit: int) -> tuple[list[dict[str, Any]], int]:
    """SPEC.md REQ-15/REQ-16: top-level search (`q`, paginowane `offset`/`limit`) albo group expansion
    (`qInclude`, zwraca wszystkie edycje danej grupy, bez paginacji — jak realne Primo dla tego trybu).

    Dopasowanie top-level: case-insensitive substring CAŁEGO zapytania względem "{title} {author}" —
    świadomie NIE tokenizacja/OR (REQ-15), żeby ogólne słowo nie trafiło przypadkiem w jeden z 3
    fikcyjnych rekordów i nie zepsuło REQ-14 (`search_books("cokolwiek")` musi zostać pusty).
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

    query_text = _parse_q(q).strip().lower()
    if not query_text:
        return [], 0

    matched_works = [work for work in _WORKS if query_text in f"{work['title']} {work['author']}".lower()]
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
