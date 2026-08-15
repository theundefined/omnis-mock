#!/usr/bin/env bash
# docs/SPEC.md REQ-12/REQ-13: prolongata — POST z ważnym tokenem realnie przesuwa duedate o +14 dni
# (stan w pamięci procesu mocka). Pokazuje termin przed i po, żeby mutacja była widoczna.
#
# UWAGA: to MUTUJE stan demo-konta na serwerze pod BASE_URL. Na lokalnym serwerze deweloperskim
# zresetujesz to restartem (uvicorn --reload); na żywym Render — dopiero jego restartem/uśpieniem.
#
# Użycie: ./07_renew_loan.sh [loan_id]   (domyślnie loan-001, ma renew="Y" w fixture)
set -euo pipefail
cd "$(dirname "$0")"
source ./lib.sh

LOAN_ID="${1:-loan-001}"
TOKEN=$(get_token)

get_due_date() {
    curl -sS "$BASE_URL/primaws/rest/priv/myaccount/loans" -H "Authorization: Bearer $TOKEN" |
        python3 -c "
import json, sys
data = json.load(sys.stdin)
loan = next((l for l in data['data']['loans']['loan'] if l['loanid'] == '$LOAN_ID'), None)
print(loan['duedate'] if loan else 'BRAK LOANU O TYM ID')
"
}

echo "Loan $LOAN_ID — duedate przed prolongatą: $(get_due_date)"

echo
echo "POST $BASE_URL/primaws/rest/priv/myaccount/renew_loans (id=$LOAN_ID)"
curl -sS -w "\nHTTP %{http_code}\n" -X POST "$BASE_URL/primaws/rest/priv/myaccount/renew_loans?lang=pl" \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d "{\"id\": \"$LOAN_ID\"}"

echo
echo "Loan $LOAN_ID — duedate po prolongacie: $(get_due_date)"
