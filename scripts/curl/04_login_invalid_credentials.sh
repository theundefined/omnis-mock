#!/usr/bin/env bash
# docs/SPEC.md REQ-1: złe dane logowania -> dokładnie 401 (omnis-py zamienia to na
# ValueError("Invalid credentials"), więc kod statusu ma znaczenie, nie tylko treść).
set -euo pipefail
cd "$(dirname "$0")"
source ./lib.sh

echo "POST $BASE_URL/primaws/suprimaLogin (złe hasło)"
curl -sS -w "\nHTTP %{http_code}\n" -X POST "$BASE_URL/primaws/suprimaLogin?lang=pl" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "authenticationProfile=Alma&username=${DEMO_USERNAME}&password=zdecydowanie-zle-haslo&institution=MOCK&view=MOCK:MOCK&targetUrl=x"
