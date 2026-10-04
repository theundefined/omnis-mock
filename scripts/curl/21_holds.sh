#!/usr/bin/env bash
# docs/SPEC.md REQ-H4..REQ-H12: zamówienia — lista, formularz, złożenie, kolejka, anulowanie.
# UWAGA: MUTUJE publiczny, współdzielony stan (REQ-H1): składa jedno zamówienie i je anuluje. Seed (REQ-H3)
# zostaje nietknięty. Zamówienie przeterminuje się samo po 24 h, a limit 5 chroni przed rozrostem (REQ-H2).
set -euo pipefail
cd "$(dirname "$0")"
source ./lib.sh

TOKEN=$(get_token)
AUTH=(-H "Authorization: Bearer $TOKEN")
MMSID="MOCK-SEARCH-A1"
ITEM="MOCK-ITEM-$MMSID-1"
ITEM_URL="$BASE_URL/primaws/rest/priv/ILSServices/itemServices/$MMSID/item/$ITEM/PS-$MMSID/AlmaItemRequest"

show_requests() {
    curl -sS "$BASE_URL/primaws/rest/priv/myaccount/requests?lang=pl" "${AUTH[@]}" | python3 -c "
import json, sys
data = json.load(sys.stdin)['data']
print('  kategorie:', sorted(data))
for h in data['holds']['hold']:
    print(f\"  {h['requestid']}: {h['title']} | {h['holdstatus']} | odbiór: {h['pickuplocationname']} | available={h['available']}\")
"
}

echo "GET myaccount/requests (start)"
show_requests

echo "GET formularz zamówienia (miejsca odbioru)"
curl -sS "$ITEM_URL?lang=pl" "${AUTH[@]}" | python3 -c "
import json, sys
group = json.load(sys.stdin)['services-arr']['services'][0]['groups-list-map'][0]
print('  materialType:', group['materialType']['key'])
for p in group['pickupLocation']:
    print(f\"  {p['key']} -> {p['value']}\")
"

echo "POST złożenie zamówienia"
curl -sS -X POST "$ITEM_URL?lang=pl" "${AUTH[@]}" -H "Content-Type: application/json" -d "{
  \"requestType\": \"hold\", \"pickupLocation\": \"MOCKLIB-FD1\", \"materialType\": \"BOOK\", \"itemId\": \"$ITEM\",
  \"group_id\": \"$MMSID\", \"pickupLibraryId\": \"MOCKLIB-FD1\", \"pickupType\": \"LIBRARY\"}"
echo

echo "GET itemQueue"
curl -sS "$BASE_URL/primaws/rest/priv/ILSServices/itemQueue/$ITEM?record-institution=MOCK&lang=pl" "${AUTH[@]}"
echo

echo "GET myaccount/requests (po złożeniu)"
show_requests

REQUEST_ID=$(curl -sS "$BASE_URL/primaws/rest/priv/myaccount/requests?lang=pl" "${AUTH[@]}" | python3 -c "
import json, sys
holds = json.load(sys.stdin)['data']['holds']['hold']
print(next(h['requestid'] for h in reversed(holds) if h['mmsid'] == '$MMSID'))
")
echo "POST cancel_requests ($REQUEST_ID)"
curl -sS -X POST "$BASE_URL/primaws/rest/priv/myaccount/cancel_requests?lang=pl" "${AUTH[@]}" \
    -H "Content-Type: application/json" -d "{\"request_id\": \"$REQUEST_ID\", \"request_type\": \"holds\"}"
echo

echo "GET myaccount/requests (po anulowaniu)"
show_requests
