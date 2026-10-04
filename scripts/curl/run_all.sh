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
# nieszkodliwe. Po dwóch prolongatach loan-001 dochodzi do `maxrenewdate` (REQ-L5) i kolejne są no-opem,
# więc przy powtarzanych uruchomieniach przeciwko tej samej, długo żyjącej instancji check akceptuje też
# termin bez zmian, o ile kolejne +14 dni przekroczyłoby `maxrenewdate`.
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

echo "-- REQ-13 / REQ-L5 --"
loan001() {
    python3 -c "import json,sys; d=json.load(sys.stdin); l=next(l for l in d['data']['loans']['loan'] if l['loanid']=='loan-001'); print(l['duedate'], l['maxrenewdate'], l['loanstatus'])"
}
read -r before max_renew _ <<<"$(echo "$LOANS_JSON" | loan001)"
curl -sS -o /dev/null -X POST "$BASE_URL/primaws/rest/priv/myaccount/renew_loans?lang=pl" \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"id":"loan-001"}'
read -r after _ status <<<"$(curl -sS "$BASE_URL/primaws/rest/priv/myaccount/loans" -H "Authorization: Bearer $TOKEN" | loan001)"
at_limit=$(python3 -c "
import sys; from datetime import datetime, timedelta
due = datetime.strptime(sys.argv[1], '%Y%m%d') + timedelta(days=14)
print(due.strftime('%Y%m%d') > sys.argv[2])" "$before" "$max_renew")
if [ "$after" \> "$before" ] && [ "$after" \< "$max_renew" -o "$after" = "$max_renew" ] && [ "$status" = "Prolongowano" ]; then
    printf "  PASS  %-55s (%s -> %s, %s)\n" "renew_loan realnie przesuwa duedate" "$before" "$after" "$status"
    PASS=$((PASS + 1))
elif [ "$after" = "$before" ] && [ "$at_limit" = "True" ]; then
    printf "  PASS  %-55s (%s, limit %s)\n" "renew_loan na limicie maxrenewdate -> bez zmian" "$after" "$max_renew"
    PASS=$((PASS + 1))
else
    printf "  FAIL  %-55s (%s -> %s, limit %s, %s)\n" "renew_loan" "$before" "$after" "$max_renew" "$status"
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

check_true() {
    local desc="$1" actual="$2"
    if [ "$actual" = "True" ]; then
        printf "  PASS  %-55s\n" "$desc"
        PASS=$((PASS + 1))
    else
        printf "  FAIL  %-55s (%s)\n" "$desc" "$actual"
        FAIL=$((FAIL + 1))
    fi
}

echo "-- REQ-G1 --"
code=$(curl -sS -o /dev/null -w "%{http_code}" "$BASE_URL/primaws/rest/pub/institution/MOCK/guestJwt")
check_status "GET /guestJwt bez parametrów -> 400" 400 "$code"
GUEST_RAW=$(curl -sS "$BASE_URL/primaws/rest/pub/institution/MOCK/guestJwt?isGuest=true&lang=pl&targetUrl=x&viewId=MOCK:MOCK")
ok=$(python3 -c "
import base64, json, sys
t = json.loads(sys.argv[1]); p = t.split('.')[1]; p += '=' * ((4 - len(p) % 4) % 4)
c = json.loads(base64.b64decode(p))
print(isinstance(t, str) and t.count('.') == 2 and c['userGroup'] == 'GUEST' and c['displayName'] is None)
" "$GUEST_RAW" 2>/dev/null || echo "błąd parsowania")
check_true "GET /guestJwt -> string JSON, 3 segmenty, userGroup=GUEST" "$ok"
GUEST_TOKEN=$(tr -d '"' <<<"$GUEST_RAW")

echo "-- REQ-G2 --"
HOLDING=$(curl -sS -X POST "$BASE_URL/primaws/rest/pub/delivery" -H "Authorization: Bearer $GUEST_TOKEN" \
    -H "Content-Type: application/json" -d '["almaMOCK-SEARCH-A2"]' |
    python3 -c "import json,sys; print(json.dumps(json.load(sys.stdin)[0]['delivery']['holding'][0]))")
for auth_desc in "tokenem gościa" "bez tokena"; do
    if [ "$auth_desc" = "tokenem gościa" ]; then AUTH=(-H "Authorization: Bearer $GUEST_TOKEN"); else AUTH=(); fi
    ok=$(curl -sS -X POST "$BASE_URL/primaws/rest/priv/ILSServices/holdings/PS-MOCK-SEARCH-A2" "${AUTH[@]}" \
        -H "Content-Type: application/json" -d "{\"locations\":[$HOLDING]}" |
        python3 -c "import json,sys; print('przekroczony' in json.load(sys.stdin)['data']['itemInfo']['locations'][0]['items'][0]['itemstatusname'])" 2>/dev/null || echo "brak terminu zwrotu")
    check_true "POST /ILSServices/holdings $auth_desc -> termin zwrotu" "$ok"
done

echo "-- REQ-G3 --"
for path in loans counters; do
    ok=$(curl -sS "$BASE_URL/primaws/rest/priv/myaccount/$path" -H "Authorization: Bearer $GUEST_TOKEN" |
        python3 -c "import json,sys; d=json.load(sys.stdin); print(d['status'] == 'failed' and d['reply-code'] == '0002')" 2>/dev/null || echo "inna odpowiedź")
    check_true "GET /$path tokenem gościa -> 200 + reply-code 0002" "$ok"
done

echo "-- REQ-G4 --"
for scope in MyInstitution MyInstitution2; do
    code=$(curl -sS -o /dev/null -w "%{http_code}" "$BASE_URL/primaws/rest/pub/pnxs?q=any,contains,Nibylandii&scope=$scope")
    check_status "GET /pnxs scope=$scope -> 200" 200 "$code"
done
code=$(curl -sS -o /dev/null -w "%{http_code}" "$BASE_URL/primaws/rest/pub/pnxs?q=any,contains,Nibylandii&scope=Bogus")
check_status "GET /pnxs nieznany scope -> 400" 400 "$code"

echo "-- REQ-G5 --"
count_docs() {
    curl -sS -G "$BASE_URL/primaws/rest/pub/pnxs" --data-urlencode "q=$1" |
        python3 -c "import json,sys; print(len(json.load(sys.stdin)['docs']))"
}
ok=$([ "$(count_docs "creator,contains,Nibylska, Karolina")" = "1" ] && echo True || echo "brak wyniku")
check_true "GET /pnxs creator z przecinkiem -> 1 wynik" "$ok"
ok=$([ "$(count_docs "creator,contains,Cienie")" = "0" ] && echo True || echo "znaleziono po tytule")
check_true "GET /pnxs creator słowem z tytułu -> 0 wyników" "$ok"

echo "-- REQ-G6 --"
ok=$(curl -sS "$BASE_URL/primaws/rest/pub/pnxs/L/almamock-mms-001?vid=MOCK:MOCK" |
    python3 -c "import json,sys; a=json.load(sys.stdin)['pnx']['addata']; print(bool(a['seriestitle']) and bool(a['au']))" 2>/dev/null || echo "brak pnx")
check_true "GET /pnxs/L/alma{mmsid} wypożyczenia -> seriestitle + au" "$ok"
ok=$([ "$(count_docs "series,contains,Dzieła wszystkie")" = "2" ] && echo True || echo "inna liczba tomów")
check_true "GET /pnxs series -> oba tomy serii" "$ok"
ok=$([ "$(count_docs "series,contains,Pan Tadeusz")" = "0" ] && echo True || echo "znaleziono po tytule")
check_true "GET /pnxs series słowem z tytułu -> 0 wyników" "$ok"
code=$(curl -sS -o /dev/null -w "%{http_code}" "$BASE_URL/primaws/rest/pub/pnxs/L/almanieistniejacy?vid=MOCK:MOCK")
check_status "GET /pnxs/L nieznany rekord -> 200 (nie 404)" 200 "$code"

echo "-- REQ-L1..L4 --"
ok=$(echo "$LOANS_JSON" | python3 -c "
import json, sys
e = json.load(sys.stdin)['data']['loans']
keys = {'callnumber2', 'year', 'itemcategoryname', 'maxrenewdate', 'renewstatuses', 'alerts', 'itemid'}
print(e['historicloans'] == 'Y' and all(keys <= l.keys() and l['duehour'] == '2359' and l['year'].endswith('.') for l in e['loan']))
" 2>/dev/null || echo "błąd parsowania")
check_true "GET /loans -> klucze REQ-L1, duehour 2359, rok z kropką" "$ok"
ok=$(echo "$LOANS_JSON" | python3 -c "
import json, sys
loans = json.load(sys.stdin)['data']['loans']['loan']
print(all(l['renewstatuses']['renewstatus'] for l in loans if l['renew'] == 'N') and any(' / ' in l['title'] for l in loans))
" 2>/dev/null || echo "błąd parsowania")
check_true "GET /loans -> komunikat przy renew=N, tytuł z „ / ”" "$ok"
ok=$(curl -sS "$BASE_URL/primaws/rest/priv/myaccount/loans?bulk=50&lang=pl&offset=1&type=history" \
    -H "Authorization: Bearer $TOKEN" | python3 -c "
import json, sys
e = json.load(sys.stdin)['data']['loans']; h = e['loan']
active = {l['loanid'] for l in json.loads(sys.argv[1])['data']['loans']['loan']}
print(3 <= len(h) <= 5 and 'Y' not in e['showmore'] and not active & {l['loanid'] for l in h}
      and all('returndate' in l and 'renewstatuses' not in l and l['renew'] == 'N' for l in h))
" "$LOANS_JSON" 2>/dev/null || echo "błąd parsowania")
check_true "GET /loans?type=history -> osobna lista ze zwrotem" "$ok"

echo "-- REQ-H4..H12 (MUTUJE stan: składa i anuluje jedno zamówienie) --"
HOLD_AUTH=(-H "Authorization: Bearer $TOKEN")
HOLD_ITEM="MOCK-ITEM-MOCK-SEARCH-A1-1"
HOLD_URL="$BASE_URL/primaws/rest/priv/ILSServices/itemServices/MOCK-SEARCH-A1/item/$HOLD_ITEM/PS-MOCK-SEARCH-A1/AlmaItemRequest"
hold_count() {
    curl -sS "$BASE_URL/primaws/rest/priv/myaccount/requests?lang=pl" "${HOLD_AUTH[@]}" |
        python3 -c "import json,sys; d=json.load(sys.stdin)['data']; print(len(d), len(d['holds']['hold']))"
}
ok=$(read -r cats before <<<"$(hold_count)"; [ "$cats" = "6" ] && echo True || echo "kategorii: $cats")
check_true "GET /requests -> 6 kategorii (REQ-H4)" "$ok"
read -r _ before <<<"$(hold_count)"
code=$(curl -sS -o /dev/null -w "%{http_code}" "$BASE_URL/primaws/rest/priv/myaccount/requests?lang=pl")
check_status "GET /requests bez tokena -> 401" 401 "$code"
ok=$(curl -sS "$BASE_URL/primaws/rest/priv/myaccount/requests" -H "Authorization: Bearer $GUEST_TOKEN" |
    python3 -c "import json,sys; d=json.load(sys.stdin); print(d['status'] == 'failed' and d['reply-code'] == '0002')" 2>/dev/null || echo "inna odpowiedź")
check_true "GET /requests tokenem gościa -> 200 + reply-code 0002" "$ok"
ok=$(curl -sS "$HOLD_URL?lang=pl" "${HOLD_AUTH[@]}" | python3 -c "
import json, sys
keys = [p['key'] for p in json.load(sys.stdin)['services-arr']['services'][0]['groups-list-map'][0]['pickupLocation']]
print(len(keys) >= 1 and all(len(k.split('\$\$')) == 2 for k in keys))" 2>/dev/null || echo "błąd parsowania")
check_true "GET formularz -> klucze <id>\$\$<TYPE> (REQ-H10a)" "$ok"
place_body() { echo "{\"requestType\":\"hold\",\"pickupLocation\":\"$1\",\"materialType\":\"BOOK\",\"itemId\":\"$HOLD_ITEM\",\"group_id\":\"MOCK-SEARCH-A1\",\"pickupLibraryId\":\"$1\",\"pickupType\":\"LIBRARY\"}"; }
code=$(curl -sS -o /dev/null -w "%{http_code}" -X POST "$HOLD_URL?lang=pl" "${HOLD_AUTH[@]}" \
    -H "Content-Type: application/json" -d "$(place_body ZLE-MIEJSCE)")
check_status "POST zamówienie ze złym miejscem odbioru -> 400" 400 "$code"
ok=$(curl -sS -X POST "$HOLD_URL?lang=pl" "${HOLD_AUTH[@]}" -H "Content-Type: application/json" -d "$(place_body MOCKLIB-FD1)" |
    python3 -c "import json,sys; d=json.load(sys.stdin); print(d['status'] == 'ok' and 'requestid' not in d)" 2>/dev/null || echo "inna odpowiedź")
check_true "POST zamówienie -> koperta ok bez requestid (REQ-H10b)" "$ok"
read -r _ after <<<"$(hold_count)"
ok=$([ "$after" -gt "$before" ] || [ "$after" = "5" ] && echo True || echo "przed=$before po=$after")
check_true "zamówienie widoczne w /requests (REQ-H10b, limit 5)" "$ok"
ok=$(curl -sS "$BASE_URL/primaws/rest/priv/ILSServices/itemQueue/$HOLD_ITEM?lang=pl" "${HOLD_AUTH[@]}" |
    python3 -c "import json,sys,re; print(bool(re.fullmatch(r'\(zamówienie: [1-9]\d*\)', json.load(sys.stdin)['itemQueueString'])))" 2>/dev/null || echo "inna odpowiedź")
check_true "GET itemQueue -> \"(zamówienie: N)\", N >= 1 (REQ-H12)" "$ok"
HOLD_ID=$(curl -sS "$BASE_URL/primaws/rest/priv/myaccount/requests?lang=pl" "${HOLD_AUTH[@]}" |
    python3 -c "import json,sys; print([h['requestid'] for h in json.load(sys.stdin)['data']['holds']['hold'] if h['mmsid'] == 'MOCK-SEARCH-A1'][-1])")
curl -sS -o /dev/null -X POST "$BASE_URL/primaws/rest/priv/myaccount/cancel_requests?lang=pl" "${HOLD_AUTH[@]}" \
    -H "Content-Type: application/json" -d "{\"request_id\":\"$HOLD_ID\",\"request_type\":\"hold\"}"
read -r _ same <<<"$(hold_count)"
ok=$([ "$same" = "$after" ] && echo True || echo "request_type=hold zmienił stan ($after -> $same)")
check_true "cancel_requests z \"hold\" (l. pojedyncza) -> bez zmiany (REQ-H11)" "$ok"
ok=$(curl -sS -X POST "$BASE_URL/primaws/rest/priv/myaccount/cancel_requests?lang=pl" "${HOLD_AUTH[@]}" \
    -H "Content-Type: application/json" -d "{\"request_id\":\"$HOLD_ID\",\"request_type\":\"holds\"}" |
    python3 -c "import json,sys; d=json.load(sys.stdin); print(d['reply-code'] == '0000' and d['data']['holds']['hold'][0]['requestid'] == '$HOLD_ID')" 2>/dev/null || echo "inna odpowiedź")
check_true "cancel_requests z \"holds\" -> koperta 0000 (REQ-H11)" "$ok"
read -r _ final <<<"$(hold_count)"
ok=$([ "$final" = "$before" ] || [ "$final" -lt "$after" ] && echo True || echo "po anulowaniu: $final")
check_true "zamówienie zniknęło po anulowaniu" "$ok"

echo "-- REQ-H7 / REQ-H8 --"
ok=$([ "$(count_docs "any,contains,MOCK-SEARCH-A1")" = "1" ] && echo True || echo "inna liczba rekordów")
check_true "GET /pnxs po samym MMS id -> dokładnie 1 rekord" "$ok"
ok=$(curl -sS "$BASE_URL/primaws/rest/pub/getPhysicalService/MOCK-SEARCH-A1" |
    python3 -c "import json,sys; print(json.load(sys.stdin)['physicalServiceId'] == 'PS-MOCK-SEARCH-A1')" 2>/dev/null || echo "brak")
check_true "getPhysicalService także dla edycji dostępnej" "$ok"

echo
echo "=== Podsumowanie: $PASS PASS, $FAIL FAIL ==="
[ "$FAIL" -eq 0 ]
