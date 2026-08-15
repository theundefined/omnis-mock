#!/usr/bin/env bash
# Uruchamia komplet testów API pod rząd i podsumowuje wynik PASS/FAIL per REQ z docs/SPEC.md.
# To NIE zastępuje tests/test_contract.py (ten uruchamia prawdziwy OmnisClient z omnis-py — silniejszy
# oracle, patrz SPEC.md "Kryterium akceptacji"). To jest szybki, zależny-tylko-od-curl smoke test,
# przydatny m.in. przeciwko żywemu deployowi na Render, gdzie pytest się nie odpala.
#
# Użycie:
#   ./run_all.sh                                          # przeciwko localhost:8000
#   BASE_URL=https://omnis-mock.onrender.com ./run_all.sh  # przeciwko żywemu deployowi
#
# UWAGA: test REQ-13 (prolongata) MUTUJE stan demo-konta (loan-001 dostaje +14 dni do terminu) —
# nieszkodliwe, ale powtarzane uruchomienia przeciwko tej samej, długo żyjącej instancji będą
# przesuwać ten termin coraz dalej w przyszłość.
set -uo pipefail
cd "$(dirname "$0")"
source ./lib.sh

PASS=0
FAIL=0

check_status() {
    local desc="$1" expected="$2" actual="$3"
    if [ "$actual" = "$expected" ]; then
        printf "  PASS  %-55s (HTTP %s)\n" "$desc" "$actual"
        PASS=$((PASS + 1))
    else
        printf "  FAIL  %-55s (oczekiwano %s, otrzymano %s)\n" "$desc" "$expected" "$actual"
        FAIL=$((FAIL + 1))
    fi
}

echo "=== omnis-mock — testy API ==="
echo "BASE_URL=$BASE_URL"
echo

echo "-- REQ-2 --"
code=$(curl -sS -o /dev/null -w "%{http_code}" "$BASE_URL/discovery/search?vid=MOCK:MOCK")
check_status "GET /discovery/search -> 200" 200 "$code"

echo "-- REQ-1 --"
code=$(curl -sS -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/primaws/suprimaLogin?lang=pl" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=${DEMO_USERNAME}&password=zle-haslo&institution=MOCK&view=MOCK:MOCK")
check_status "POST /suprimaLogin złym hasłem -> 401" 401 "$code"

echo "-- REQ-3 / REQ-4 --"
TOKEN=$(get_token)
if [ -n "$TOKEN" ] && [ "$(echo -n "$TOKEN" | tr -dc '.' | wc -c)" = "2" ]; then
    printf "  PASS  %-55s\n" "login zwrócił token o 3 segmentach"
    PASS=$((PASS + 1))
else
    printf "  FAIL  %-55s\n" "login nie zwrócił poprawnego tokenu"
    FAIL=$((FAIL + 1))
fi

echo "-- REQ-5 / REQ-8 / REQ-12 --"
code=$(curl -sS -o /dev/null -w "%{http_code}" "$BASE_URL/primaws/rest/priv/myaccount/counters?lang=pl")
check_status "GET /counters bez tokena -> 401" 401 "$code"
code=$(curl -sS -o /dev/null -w "%{http_code}" "$BASE_URL/primaws/rest/priv/myaccount/loans")
check_status "GET /loans bez tokena -> 401" 401 "$code"
code=$(curl -sS -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/primaws/rest/priv/myaccount/renew_loans?lang=pl" \
    -H "Content-Type: application/json" -d '{"id":"loan-001"}')
check_status "POST /renew_loans bez tokena -> 401" 401 "$code"

echo "-- REQ-6 / REQ-7 --"
code=$(curl -sS -o /dev/null -w "%{http_code}" "$BASE_URL/primaws/rest/priv/myaccount/counters?lang=pl" \
    -H "Authorization: Bearer $TOKEN")
check_status "GET /counters z tokenem -> 200" 200 "$code"

echo "-- REQ-9 / REQ-10 / REQ-11 --"
LOANS_JSON=$(curl -sS "$BASE_URL/primaws/rest/priv/myaccount/loans" -H "Authorization: Bearer $TOKEN")
loan_count=$(echo "$LOANS_JSON" | python3 -c "import json,sys; print(len(json.load(sys.stdin)['data']['loans']['loan']))" 2>/dev/null || echo "0")
if [ "$loan_count" -ge 1 ] && [ "$loan_count" -lt 50 ]; then
    printf "  PASS  %-55s (%s loanów)\n" "GET /loans zwraca < 50 pozycji" "$loan_count"
    PASS=$((PASS + 1))
else
    printf "  FAIL  %-55s (%s loanów)\n" "GET /loans — niespodziewana liczba pozycji" "$loan_count"
    FAIL=$((FAIL + 1))
fi

echo "-- REQ-13 --"
before=$(echo "$LOANS_JSON" | python3 -c "import json,sys; d=json.load(sys.stdin); print(next(l['duedate'] for l in d['data']['loans']['loan'] if l['loanid']=='loan-001'))")
curl -sS -o /dev/null -X POST "$BASE_URL/primaws/rest/priv/myaccount/renew_loans?lang=pl" \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"id":"loan-001"}'
after=$(curl -sS "$BASE_URL/primaws/rest/priv/myaccount/loans" -H "Authorization: Bearer $TOKEN" |
    python3 -c "import json,sys; d=json.load(sys.stdin); print(next(l['duedate'] for l in d['data']['loans']['loan'] if l['loanid']=='loan-001'))")
if [ "$before" != "$after" ]; then
    printf "  PASS  %-55s (%s -> %s)\n" "renew_loan realnie przesuwa duedate" "$before" "$after"
    PASS=$((PASS + 1))
else
    printf "  FAIL  %-55s (bez zmian: %s)\n" "renew_loan nie przesunął duedate" "$before"
    FAIL=$((FAIL + 1))
fi

echo "-- REQ-13b --"
code=$(curl -sS -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/primaws/rest/priv/myaccount/renew_loans?lang=pl" \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"id":"nieistniejacy-id"}')
check_status "POST /renew_loans nieznanym id -> 200 no-op" 200 "$code"

echo "-- REQ-14 --"
docs_len=$(curl -sS "$BASE_URL/primaws/rest/pub/pnxs?q=any,contains,cokolwiek" |
    python3 -c "import json,sys; print(len(json.load(sys.stdin)['docs']))")
if [ "$docs_len" = "0" ]; then
    printf "  PASS  %-55s\n" "GET /pnxs (niepasujące zapytanie) zwraca pustą listę"
    PASS=$((PASS + 1))
else
    printf "  FAIL  %-55s (docs_len=%s)\n" "GET /pnxs" "$docs_len"
    FAIL=$((FAIL + 1))
fi

echo "-- REQ-15 / REQ-16 --"
SEARCH_JSON=$(curl -sS -G "$BASE_URL/primaws/rest/pub/pnxs" --data-urlencode "q=any,contains,Nibylandii")
docs_len=$(echo "$SEARCH_JSON" | python3 -c "import json,sys; print(len(json.load(sys.stdin)['docs']))")
if [ "$docs_len" = "1" ]; then
    printf "  PASS  %-55s\n" "GET /pnxs (trafiające zapytanie) zwraca 1 doc"
    PASS=$((PASS + 1))
else
    printf "  FAIL  %-55s (docs_len=%s)\n" "GET /pnxs trafiające" "$docs_len"
    FAIL=$((FAIL + 1))
fi

GROUP_JSON=$(curl -sS -G "$BASE_URL/primaws/rest/pub/pnxs" \
    --data-urlencode "q=any,contains,Nibylandii" \
    --data-urlencode "qInclude=facet_frbrgroupid,exact,MOCK-GROUP-A")
group_len=$(echo "$GROUP_JSON" | python3 -c "import json,sys; print(len(json.load(sys.stdin)['docs']))")
if [ "$group_len" = "2" ]; then
    printf "  PASS  %-55s\n" "GET /pnxs (qInclude) zwraca obie edycje"
    PASS=$((PASS + 1))
else
    printf "  FAIL  %-55s (group_len=%s)\n" "GET /pnxs qInclude" "$group_len"
    FAIL=$((FAIL + 1))
fi

echo "-- REQ-17 --"
DELIVERY_JSON=$(curl -sS -X POST "$BASE_URL/primaws/rest/pub/delivery" \
    -H "Content-Type: application/json" -d '["almaMOCK-SEARCH-A1","almaMOCK-SEARCH-A2"]')
holkey_present=$(echo "$DELIVERY_JSON" |
    python3 -c "import json,sys; d=json.load(sys.stdin); print(all('holKey' in item['delivery']['holding'][0] and item['delivery']['holding'][0]['holKey'] for item in d))")
if [ "$holkey_present" = "True" ]; then
    printf "  PASS  %-55s\n" "POST /delivery zwraca holKey dla każdego holdingu"
    PASS=$((PASS + 1))
else
    printf "  FAIL  %-55s\n" "POST /delivery — brak holKey"
    FAIL=$((FAIL + 1))
fi

echo "-- REQ-18 --"
code=$(curl -sS -o /dev/null -w "%{http_code}" "$BASE_URL/primaws/rest/pub/getPhysicalService/nieznany-mmsid")
check_status "GET /getPhysicalService nieznanym mmsid -> 404" 404 "$code"

echo "-- REQ-18b --"
code=$(curl -sS -o /dev/null -w "%{http_code}" -X POST \
    "$BASE_URL/primaws/rest/priv/ILSServices/holdings/PS-MOCK-SEARCH-A2" \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d '{"locations":[{"mainLocation":"Filia Demo 2"}]}')
check_status "POST /ILSServices/holdings bez holKey -> 200 (nie 404)" 200 "$code"

body=$(curl -sS -X POST \
    "$BASE_URL/primaws/rest/priv/ILSServices/holdings/PS-MOCK-SEARCH-A2" \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d '{"locations":[{"mainLocation":"Filia Demo 2"}]}')
if [ "$body" = '{"data":{"itemInfo":{"locations":[]}}}' ]; then
    printf "  PASS  %-55s\n" "POST /ILSServices/holdings bez holKey -> pusta locations"
    PASS=$((PASS + 1))
else
    printf "  FAIL  %-55s (otrzymano: %s)\n" "POST /ILSServices/holdings bez holKey" "$body"
    FAIL=$((FAIL + 1))
fi

echo
echo "=== Podsumowanie: $PASS PASS, $FAIL FAIL ==="
[ "$FAIL" -eq 0 ]
