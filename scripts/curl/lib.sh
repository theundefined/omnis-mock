#!/usr/bin/env bash
# Współdzielone zmienne i pomocnicza funkcja logowania.
# Nie uruchamiaj bezpośrednio — jest "source"-owany przez pozostałe skrypty w tym katalogu.
#
# Zmienne środowiskowe (wszystkie opcjonalne, z sensownymi domyślnymi):
#   BASE_URL        adres mocka (domyślnie lokalny serwer deweloperski)
#   DEMO_USERNAME   login konta demo (musi się zgadzać z tym, na czym stoi serwer pod BASE_URL)
#   DEMO_PASSWORD   hasło konta demo
#
# Przykład wskazania na żywy deploy zamiast localhost:
#   BASE_URL=https://omnis-mock.onrender.com ./05_counters.sh

BASE_URL="${BASE_URL:-http://localhost:8000}"
DEMO_USERNAME="${DEMO_USERNAME:-demo}"
DEMO_PASSWORD="${DEMO_PASSWORD:-demo1234}"

# Loguje się i wypisuje SAM token JWT na stdout (nic więcej) — do użycia jako:
#   TOKEN=$(get_token)
get_token() {
    local response
    response=$(curl -sS -X POST "$BASE_URL/primaws/suprimaLogin?lang=pl" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "authenticationProfile=Alma&username=${DEMO_USERNAME}&password=${DEMO_PASSWORD}&institution=MOCK&view=MOCK:MOCK&targetUrl=x")
    python3 -c "import json,sys; print(json.load(sys.stdin)['jwtData'])" <<<"$response"
}
