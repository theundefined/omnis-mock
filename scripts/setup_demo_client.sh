#!/usr/bin/env bash
# Tworzy izolowane środowisko (osobny venv + osobny "HOME") z prawdziwym omnis-py z PyPI,
# skonfigurowanym pod ten mock — do ręcznego eksplorowania API przez omnis-cli.
#
# CELOWO izolowane: konfiguracja omnis-cli trafia do ./demo-client/home/.config/omnis-py/config.yaml,
# NIE do prawdziwego ~/.config/omnis-py/config.yaml — jeśli masz tam realne konto biblioteczne, ten
# skrypt go nie dotyka i nigdy nie doda do niego wpisu o mocku.
#
# Użycie:
#   ./scripts/setup_demo_client.sh                                   # BASE_URL=http://localhost:8000
#   ./scripts/setup_demo_client.sh https://omnis-mock.onrender.com   # przeciwko żywemu deployowi
#
# Po zakończeniu:
#   ./demo-client/bin/omnis-cli-demo               # domyślny widok tabelaryczny
#   ./demo-client/bin/omnis-cli-demo --renew        # prolongata
#   ./demo-client/bin/omnis-cli-demo --format json
set -euo pipefail
cd "$(dirname "$0")/.."  # katalog główny omnis-mock

BASE_URL="${1:-http://localhost:8000}"
DEMO_USERNAME="${DEMO_USERNAME:-demo}"
DEMO_PASSWORD="${DEMO_PASSWORD:-demo1234}"
DEMO_DIR="demo-client"

echo "==> Tworzę izolowane środowisko w ./${DEMO_DIR}/"
echo "    BASE_URL = $BASE_URL"

rm -rf "$DEMO_DIR"
mkdir -p "$DEMO_DIR/home/.config/omnis-py" "$DEMO_DIR/bin"

python3 -m venv "$DEMO_DIR/venv"
"$DEMO_DIR/venv/bin/pip" install --quiet --upgrade pip
"$DEMO_DIR/venv/bin/pip" install --quiet omnis-py

cat >"$DEMO_DIR/home/.config/omnis-py/config.yaml" <<EOF
accounts:
  - username: ${DEMO_USERNAME}
    password: ${DEMO_PASSWORD}
    base_url: ${BASE_URL}
    institution: MOCK
    view: "MOCK:MOCK"
    tenant_name: "omnis-mock (${BASE_URL})"
EOF

cat >"$DEMO_DIR/bin/omnis-cli-demo" <<'EOF'
#!/usr/bin/env bash
# Wrapper wygenerowany przez ../../scripts/setup_demo_client.sh: uruchamia omnis-cli z izolowanym
# HOME, żeby NIGDY nie dotykał prawdziwego ~/.config/omnis-py/config.yaml użytkownika.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec env HOME="$HERE/home" "$HERE/venv/bin/omnis-cli" "$@"
EOF
chmod +x "$DEMO_DIR/bin/omnis-cli-demo"

echo
echo "Gotowe. Prawdziwy ~/.config/omnis-py/config.yaml NIE został dotknięty."
echo
echo "Użycie:"
echo "  ./${DEMO_DIR}/bin/omnis-cli-demo               # widok tabelaryczny"
echo "  ./${DEMO_DIR}/bin/omnis-cli-demo --renew        # prolongata"
echo "  ./${DEMO_DIR}/bin/omnis-cli-demo --format json"
echo
echo "Żeby wskazać inny URL mocka (np. Render zamiast localhost), uruchom ponownie z argumentem:"
echo "  ./scripts/setup_demo_client.sh https://omnis-mock.onrender.com"
