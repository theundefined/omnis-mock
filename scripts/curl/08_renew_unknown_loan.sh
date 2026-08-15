#!/usr/bin/env bash
# docs/SPEC.md REQ-13b: nieznany loan_id -> 200 no-op (NIE 404/500) — omnis-py nie obsługuje specjalnie
# żadnego innego kodu błędu tutaj poza raise_for_status(), więc każdy nie-2xx wysypałby klienta.
set -euo pipefail
cd "$(dirname "$0")"
source ./lib.sh

TOKEN=$(get_token)

echo "POST $BASE_URL/primaws/rest/priv/myaccount/renew_loans (nieistniejące id)"
curl -sS -w "\nHTTP %{http_code}\n" -X POST "$BASE_URL/primaws/rest/priv/myaccount/renew_loans?lang=pl" \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d '{"id": "totally-bogus-loan-id-xyz"}'
