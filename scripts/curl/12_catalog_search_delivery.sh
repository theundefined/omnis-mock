#!/usr/bin/env bash
# docs/SPEC.md REQ-17: dostępność per filia dla obu wydań "Cienie Nibylandii" (alma-id z fixture,
# src/omnis_mock/search_data.py). Body to goła lista stringów JSON — dokładnie to, co wysyła omnis-py.
set -euo pipefail
cd "$(dirname "$0")"
source ./lib.sh

echo "POST /primaws/rest/pub/delivery"
curl -sS -w "\nHTTP %{http_code}\n" -X POST \
    "$BASE_URL/primaws/rest/pub/delivery" \
    -H "Content-Type: application/json;charset=UTF-8" \
    -d '["almaMOCK-SEARCH-A1", "almaMOCK-SEARCH-A2"]'
