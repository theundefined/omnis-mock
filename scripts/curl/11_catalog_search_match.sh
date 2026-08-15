#!/usr/bin/env bash
# docs/SPEC.md REQ-15/REQ-16: /pnxs zwraca realne (fikcyjne) wyniki dla zapytań trafiających fixture
# (src/omnis_mock/search_data.py). Top-level search + group expansion (qInclude) dla "Cienie Nibylandii",
# które ma 2 wydania.
set -euo pipefail
cd "$(dirname "$0")"
source ./lib.sh

echo "GET /primaws/rest/pub/pnxs (top-level, trafiające zapytanie)"
curl -sS -w "\nHTTP %{http_code}\n" \
    --data-urlencode "q=any,contains,Nibylandii" \
    -G "$BASE_URL/primaws/rest/pub/pnxs"

echo
echo "GET /primaws/rest/pub/pnxs (group expansion, qInclude=frbrgroupid MOCK-GROUP-A)"
curl -sS -w "\nHTTP %{http_code}\n" \
    --data-urlencode "q=any,contains,Nibylandii" \
    --data-urlencode "qInclude=facet_frbrgroupid,exact,MOCK-GROUP-A" \
    --data-urlencode "sort=date_d" \
    -G "$BASE_URL/primaws/rest/pub/pnxs"
