#!/usr/bin/env bash
# docs/SPEC.md REQ-G3 (pułapka): token gościa NIE daje dostępu do konta — myaccount/* zwraca 200 (NIE 401!)
# z "status":"failed", "reply-code":"0002". Klient sprawdzający tylko kod HTTP uzna to za sukces.
# renew_loans tokenem gościa niczego nie mutuje.
set -euo pipefail
cd "$(dirname "$0")"
source ./lib.sh

GUEST_TOKEN=$(get_guest_token)

echo "GET /primaws/rest/priv/myaccount/loans (token gościa)"
curl -sS -w "\nHTTP %{http_code}\n" "$BASE_URL/primaws/rest/priv/myaccount/loans" \
    -H "Authorization: Bearer $GUEST_TOKEN"

echo
echo "GET /primaws/rest/priv/myaccount/counters (token gościa)"
curl -sS -w "\nHTTP %{http_code}\n" "$BASE_URL/primaws/rest/priv/myaccount/counters?lang=pl" \
    -H "Authorization: Bearer $GUEST_TOKEN"

echo
echo "POST /primaws/rest/priv/myaccount/renew_loans (token gościa)"
curl -sS -w "\nHTTP %{http_code}\n" -X POST "$BASE_URL/primaws/rest/priv/myaccount/renew_loans?lang=pl" \
    -H "Authorization: Bearer $GUEST_TOKEN" -H "Content-Type: application/json" -d '{"id":"loan-001"}'
