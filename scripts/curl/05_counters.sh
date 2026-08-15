#!/usr/bin/env bash
# docs/SPEC.md REQ-5/REQ-6/REQ-7: stan konta. UWAGA REQ-7: Fines.value w formacie z KROPKĄ ("0.00"),
# inny niż format w /fines (poza zakresem Layer 1) — to celowa niespójność prawdziwego Primo, nie błąd.
set -euo pipefail
cd "$(dirname "$0")"
source ./lib.sh

TOKEN=$(get_token)

echo "GET $BASE_URL/primaws/rest/priv/myaccount/counters"
curl -sS -w "\nHTTP %{http_code}\n" "$BASE_URL/primaws/rest/priv/myaccount/counters?lang=pl" \
    -H "Authorization: Bearer $TOKEN"
