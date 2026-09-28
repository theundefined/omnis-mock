#!/usr/bin/env bash
# docs/SPEC.md REQ-L1..REQ-L4: pełny kształt wypożyczeń (okno „Szczegóły” w omnis-mobile) i osobna historia
# (`type=history`). Pokazuje skrót pól, które widać w oknie szczegółów, dla aktywnych i dla historii.
set -euo pipefail
cd "$(dirname "$0")"
source ./lib.sh

TOKEN=$(get_token)

for loan_type in active history; do
    echo "GET $BASE_URL/primaws/rest/priv/myaccount/loans?type=$loan_type"
    curl -sS "$BASE_URL/primaws/rest/priv/myaccount/loans?bulk=50&lang=pl&offset=1&type=$loan_type" \
        -H "Authorization: Bearer $TOKEN" | python3 -c "
import json, sys
envelope = json.load(sys.stdin)['data']['loans']
print(f\"  showmore={envelope['showmore']} historicloans={envelope.get('historicloans')} hasAlerts={envelope.get('hasAlerts')}\")
for loan in envelope['loan']:
    print(f\"  {loan['loanid']}: {loan['title']}\")
    print(f\"    status={loan['loanstatus']} rok={loan.get('year')} sygn.={loan.get('callnumber2')} kat.={loan.get('itemcategoryname')}\")
    print(f\"    filia={loan['mainlocationname']} ({loan['secondarylocationname']}) termin={loan['duedate']} {loan['duehour']}\")
    if 'returndate' in loan:
        print(f\"    zwrócono={loan['returndate']} {loan['returnhour']}\")
    else:
        print(f\"    prolongata do={loan['maxrenewdate']} renew={loan['renew']} powód={loan['renewstatuses']['renewstatus']}\")
"
    echo
done
