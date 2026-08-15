#!/usr/bin/env bash
# docs/SPEC.md REQ-18b (pułapka): termin zwrotu rozwiązuje się TYLKO gdy body zawiera niepusty `holKey`
# w `locations[0]`. Pierwsze wywołanie przekazuje pełny holding z 12_catalog_search_delivery.sh (z
# holKey) -> dane; drugie przekazuje holding bez holKey -> 200 z pustą listą `items`, NIE 404.
set -euo pipefail
cd "$(dirname "$0")"
source ./lib.sh

TOKEN=$(get_token)

echo "POST /primaws/rest/priv/ILSServices/holdings/PS-MOCK-SEARCH-A2 (Z holKey -> termin zwrotu)"
curl -sS -w "\nHTTP %{http_code}\n" -X POST \
    "$BASE_URL/primaws/rest/priv/ILSServices/holdings/PS-MOCK-SEARCH-A2?record-institution=MOCK&lang=pl" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json;charset=UTF-8" \
    -d '{"filters":{"noItem":10,"sublibrary":"Filia Demo 2","holid":"MOCK-HOLD-A2"},"locations":[{"mainLocation":"Filia Demo 2","holdId":"MOCK-HOLD-A2","holKey":"HoldingResultKey [mid=MOCK-HOLD-A2, libraryId=MOCK-LIB-FD2, locationCode=FD2dz, callNumber=null]"}],"hideResourceSharing":false}'

echo
echo "POST /primaws/rest/priv/ILSServices/holdings/PS-MOCK-SEARCH-A2 (BEZ holKey -> pusta lista items, REQ-18b)"
curl -sS -w "\nHTTP %{http_code}\n" -X POST \
    "$BASE_URL/primaws/rest/priv/ILSServices/holdings/PS-MOCK-SEARCH-A2?record-institution=MOCK&lang=pl" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json;charset=UTF-8" \
    -d '{"filters":{"noItem":10,"sublibrary":"Filia Demo 2","holid":"MOCK-HOLD-A2"},"locations":[{"mainLocation":"Filia Demo 2","holdId":"MOCK-HOLD-A2"}],"hideResourceSharing":false}'
