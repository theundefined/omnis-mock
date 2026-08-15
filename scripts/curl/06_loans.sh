#!/usr/bin/env bash
# docs/SPEC.md REQ-8/REQ-9/REQ-10/REQ-11: lista wypożyczeń demo-konta.
set -euo pipefail
cd "$(dirname "$0")"
source ./lib.sh

TOKEN=$(get_token)

echo "GET $BASE_URL/primaws/rest/priv/myaccount/loans"
curl -sS -w "\nHTTP %{http_code}\n" \
    "$BASE_URL/primaws/rest/priv/myaccount/loans?bulk=50&lang=pl&offset=1&type=active" \
    -H "Authorization: Bearer $TOKEN"
