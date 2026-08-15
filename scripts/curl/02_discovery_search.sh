#!/usr/bin/env bash
# docs/SPEC.md REQ-2: cookie-priming w prawdziwym Primo. Powinno zawsze zwrócić 200, bez auth.
set -euo pipefail
cd "$(dirname "$0")"
source ./lib.sh

echo "GET $BASE_URL/discovery/search?vid=MOCK:MOCK"
curl -sS -w "\nHTTP %{http_code}\n" "$BASE_URL/discovery/search?vid=MOCK:MOCK"
