#!/usr/bin/env bash
# docs/SPEC.md REQ-18: id usługi fizycznej dla niedostępnego wydania "Cienie Nibylandii" (MOCK-SEARCH-A2),
# potrzebny w kolejnym kroku (14_ils_holdings.sh) do rozwiązania terminu zwrotu. Drugi wywołanie pokazuje
# 404 dla nieznanego mmsid.
set -euo pipefail
cd "$(dirname "$0")"
source ./lib.sh

echo "GET /primaws/rest/pub/getPhysicalService/MOCK-SEARCH-A2 (znany, niedostępny)"
curl -sS -w "\nHTTP %{http_code}\n" "$BASE_URL/primaws/rest/pub/getPhysicalService/MOCK-SEARCH-A2?vid=MOCK:MOCK&lang=pl&recordOwner=MOCK&sourceRecordId=MOCK-SEARCH-A2&resource_type=book&isRapido=false"

echo
echo "GET /primaws/rest/pub/getPhysicalService/nieznany-mmsid (-> 404)"
curl -sS -w "\nHTTP %{http_code}\n" "$BASE_URL/primaws/rest/pub/getPhysicalService/nieznany-mmsid"
