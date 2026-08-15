#!/usr/bin/env bash
# docs/SPEC.md REQ-5/REQ-8/REQ-12: wszystkie trzy prywatne endpointy bez nagłówka Authorization
# muszą zwrócić dokładnie 401, nie 403/404/500.
set -euo pipefail
cd "$(dirname "$0")"
source ./lib.sh

echo "GET  /myaccount/counters   (bez Authorization)"
curl -sS -o /dev/null -w "  -> HTTP %{http_code}\n" "$BASE_URL/primaws/rest/priv/myaccount/counters?lang=pl"

echo "GET  /myaccount/loans      (bez Authorization)"
curl -sS -o /dev/null -w "  -> HTTP %{http_code}\n" "$BASE_URL/primaws/rest/priv/myaccount/loans"

echo "POST /myaccount/renew_loans (bez Authorization)"
curl -sS -o /dev/null -w "  -> HTTP %{http_code}\n" -X POST "$BASE_URL/primaws/rest/priv/myaccount/renew_loans?lang=pl" \
    -H "Content-Type: application/json" -d '{"id": "loan-001"}'
