#!/usr/bin/env bash
# docs/SPEC.md REQ-G5: wyszukiwanie po autorze. Wartość addata.au z wyniku ("Nazwisko, Imię" — z
# przecinkiem!) wysłana jako q=creator,contains,<au> musi wrócić do tego samego rekordu; słowo z TYTUŁU w
# polu creator nie znajduje nic (w any — znajduje).
set -euo pipefail
cd "$(dirname "$0")"
source ./lib.sh

titles() {
    curl -sS -G "$BASE_URL/primaws/rest/pub/pnxs" --data-urlencode "q=$1" -d scope=MyInstitution -d vid=MOCK:MOCK |
        python3 -c "import json,sys; print([d['pnx']['addata']['btitle'][0] for d in json.load(sys.stdin)['docs']])"
}

AU=$(curl -sS -G "$BASE_URL/primaws/rest/pub/pnxs" --data-urlencode "q=any,contains,Nibylandii" -d scope=MyInstitution |
    python3 -c "import json,sys; print(json.load(sys.stdin)['docs'][0]['pnx']['addata']['au'][0])")
echo "addata.au z wyniku 'Nibylandii': $AU"
echo

for q in "creator,contains,$AU" "creator,contains,Cienie" "any,contains,Cienie" "creator,contains,Mickiewicz, Adam"; do
    printf "%-40s -> %s\n" "q=$q" "$(titles "$q")"
done
