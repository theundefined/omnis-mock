#!/usr/bin/env bash
# docs/SPEC.md REQ-G6: rekord wypożyczenia (pnxs/L/alma{mmsid}, bez tokena) niesie addata.seriestitle i
# addata.au; nazwa serii przycięta jak w omnis-mobile (do pierwszego ";" i " / ") wysłana jako
# q=series,contains,<nazwa> zwraca oba tomy serii. Nieznany rekord -> 200 bez "pnx" (nie 404).
set -euo pipefail
cd "$(dirname "$0")"
source ./lib.sh

echo "GET /primaws/rest/pub/pnxs/L/almamock-mms-001 (Pan Tadeusz — wypożyczenie demo)"
RECORD_JSON=$(curl -sS "$BASE_URL/primaws/rest/pub/pnxs/L/almamock-mms-001?vid=MOCK:MOCK&lang=pl")
python3 -c "import json,sys; a=json.load(sys.stdin)['pnx']['addata']; print('    au:', a['au'], '| seriestitle:', a['seriestitle'])" <<<"$RECORD_JSON"
TERM_=$(python3 -c "
import json, re, sys
s = json.load(sys.stdin)['pnx']['addata']['seriestitle'][0]
print(re.split(r'\s+/\s+', s.split(';', 1)[0], maxsplit=1)[0].strip().rstrip('.,:').strip())" <<<"$RECORD_JSON")
echo "    nazwa serii do wyszukania: $TERM_"

echo
for q in "series,contains,$TERM_" "series,contains,Pan Tadeusz"; do
    titles=$(curl -sS -G "$BASE_URL/primaws/rest/pub/pnxs" --data-urlencode "q=$q" -d scope=MyInstitution -d vid=MOCK:MOCK |
        python3 -c "import json,sys; print([d['pnx']['addata']['btitle'][0] for d in json.load(sys.stdin)['docs']])")
    printf "%-40s -> %s\n" "q=$q" "$titles"
done

echo
echo "GET /primaws/rest/pub/pnxs/L/almanieistniejacy (nieznany rekord -> 200 bez pnx)"
curl -sS -w "\nHTTP %{http_code}\n" "$BASE_URL/primaws/rest/pub/pnxs/L/almanieistniejacy?vid=MOCK:MOCK&lang=pl"
