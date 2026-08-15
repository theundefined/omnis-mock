#!/usr/bin/env bash
# docs/SPEC.md REQ-3/REQ-4: logowanie poprawnymi danymi demo-konta. Powinno zwrócić
# {"jwtData": "<3-segmentowy token>"} — dekodujemy payload lokalnie, żeby pokazać displayName/userName
# (dokładnie tak, jak robi to prawdziwy omnis-py, patrz OmnisClient.get_user_info()).
set -euo pipefail
cd "$(dirname "$0")"
source ./lib.sh

echo "POST $BASE_URL/primaws/suprimaLogin (username=$DEMO_USERNAME)"
RESPONSE=$(curl -sS -w "\nHTTP %{http_code}" -X POST "$BASE_URL/primaws/suprimaLogin?lang=pl" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "authenticationProfile=Alma&username=${DEMO_USERNAME}&password=${DEMO_PASSWORD}&institution=MOCK&view=MOCK:MOCK&targetUrl=x")
echo "$RESPONSE"

TOKEN=$(get_token)
echo
echo "Zdekodowany payload JWT:"
PAYLOAD="${TOKEN#*.}"
PAYLOAD="${PAYLOAD%.*}"
python3 -c "
import base64, json, sys
payload = sys.argv[1]
payload += '=' * ((4 - len(payload) % 4) % 4)
print(json.dumps(json.loads(base64.b64decode(payload)), ensure_ascii=False, indent=2))
" "$PAYLOAD"
