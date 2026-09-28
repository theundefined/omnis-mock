#!/usr/bin/env bash
# docs/SPEC.md REQ-G2 (+ REQ-G4): cały pipeline wyszukiwarki tokenem gościa, bez logowania — dokładnie to,
# co robi omnis-mobile: pnxs (scope=MyInstitution) -> delivery -> getPhysicalService ->
# ILSServices/holdings (z holdingiem 1:1 z delivery, czyli z holKey) -> termin zwrotu.
set -euo pipefail
cd "$(dirname "$0")"
source ./lib.sh

GUEST_TOKEN=$(get_guest_token)
AUTH=(-H "Authorization: Bearer $GUEST_TOKEN")

echo "1. GET /primaws/rest/pub/pnxs (q=any,contains,Nibylandii, scope=MyInstitution)"
SEARCH_JSON=$(curl -sS -G "$BASE_URL/primaws/rest/pub/pnxs" "${AUTH[@]}" \
    --data-urlencode "q=any,contains,Nibylandii" -d vid=MOCK:MOCK -d inst=MOCK \
    -d scope=MyInstitution -d tab=LibraryCatalog -d limit=10 -d offset=0 -d lang=pl)
python3 -c "import json,sys; d=json.load(sys.stdin); [print('   ', doc['pnx']['control']['recordid'][0], '|', doc['pnx']['addata']['btitle'][0], '|', doc['pnx']['addata']['au'][0]) for doc in d['docs']]" <<<"$SEARCH_JSON"

echo
echo "2. POST /primaws/rest/pub/delivery dla niedostępnej edycji (almaMOCK-SEARCH-A2)"
DELIVERY_JSON=$(curl -sS -X POST "$BASE_URL/primaws/rest/pub/delivery" "${AUTH[@]}" \
    -H "Content-Type: application/json;charset=UTF-8" -d '["almaMOCK-SEARCH-A2"]')
HOLDING=$(python3 -c "import json,sys; print(json.dumps(json.load(sys.stdin)[0]['delivery']['holding'][0]))" <<<"$DELIVERY_JSON")
python3 -c "import json,sys; h=json.load(sys.stdin); print('    availabilityStatus:', h['availabilityStatus']); print('    holKey:', h['holKey'])" <<<"$HOLDING"

echo
echo "3. GET /primaws/rest/pub/getPhysicalService/MOCK-SEARCH-A2"
PS_ID=$(curl -sS "$BASE_URL/primaws/rest/pub/getPhysicalService/MOCK-SEARCH-A2" "${AUTH[@]}" |
    python3 -c "import json,sys; print(json.load(sys.stdin)['physicalServiceId'])")
echo "    physicalServiceId: $PS_ID"

echo
echo "4. POST /primaws/rest/priv/ILSServices/holdings/$PS_ID (token gościa, holding z kroku 2)"
curl -sS -w "\nHTTP %{http_code}\n" -X POST \
    "$BASE_URL/primaws/rest/priv/ILSServices/holdings/$PS_ID?record-institution=MOCK&lang=pl" "${AUTH[@]}" \
    -H "Content-Type: application/json;charset=UTF-8" \
    -d "{\"locations\":[$HOLDING],\"hideResourceSharing\":false}"
