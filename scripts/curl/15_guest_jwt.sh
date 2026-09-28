#!/usr/bin/env bash
# docs/SPEC.md REQ-G1: token gościa do anonimowego wyszukiwania. Body to LITERAŁ stringu JSON (token w
# cudzysłowach, nie obiekt {"jwtData": ...} jak w suprimaLogin). Drugie wywołanie bez parametrów -> 400.
set -euo pipefail
cd "$(dirname "$0")"
source ./lib.sh

echo "GET /primaws/rest/pub/institution/MOCK/guestJwt?isGuest=true&lang=pl&targetUrl=x&viewId=MOCK:MOCK"
curl -sS -i "$BASE_URL/primaws/rest/pub/institution/MOCK/guestJwt?isGuest=true&lang=pl&targetUrl=x&viewId=MOCK:MOCK"
echo
echo

echo "Zdekodowany payload tokena gościa:"
GUEST_TOKEN=$(get_guest_token)
python3 - "$GUEST_TOKEN" <<'EOF'
import base64, json, sys
payload = sys.argv[1].split(".")[1]
payload += "=" * ((4 - len(payload) % 4) % 4)
print(json.dumps(json.loads(base64.b64decode(payload)), indent=2))
EOF

echo
echo "GET /primaws/rest/pub/institution/MOCK/guestJwt (bez parametrów -> 400)"
curl -sS -w "HTTP %{http_code}\n" "$BASE_URL/primaws/rest/pub/institution/MOCK/guestJwt"
