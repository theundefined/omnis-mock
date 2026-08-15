#!/usr/bin/env bash
# docs/SPEC.md REQ-14: zapytanie niczego nie trafiające w fixture (src/omnis_mock/search_data.py) zwraca
# {"docs": [], "info": {...}}, z tokenem lub bez. Dla trafiającego zapytania (Layer 2, REQ-15/REQ-16) patrz
# 11_catalog_search_match.sh.
set -euo pipefail
cd "$(dirname "$0")"
source ./lib.sh

echo "GET $BASE_URL/primaws/rest/pub/pnxs (niepasujące query, bez auth)"
curl -sS -w "\nHTTP %{http_code}\n" "$BASE_URL/primaws/rest/pub/pnxs?q=any,contains,cokolwiek"
