#!/usr/bin/env bash
# docs/SPEC.md REQ-14: /pnxs to bezpiecznik dla SearchScreen w omnis-mobile (Layer 2 — pełny mock
# wyszukiwarki — jest poza zakresem tego serwera), zawsze zwraca {"docs": []}, z tokenem lub bez.
set -euo pipefail
cd "$(dirname "$0")"
source ./lib.sh

echo "GET $BASE_URL/primaws/rest/pub/pnxs (dowolne query, bez auth)"
curl -sS -w "\nHTTP %{http_code}\n" "$BASE_URL/primaws/rest/pub/pnxs?q=any,contains,cokolwiek"
