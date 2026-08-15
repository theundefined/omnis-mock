#!/usr/bin/env bash
# Health check — endpoint używany przez Render jako healthCheckPath (patrz ../../render.yaml).
# Nie wymaga logowania.
set -euo pipefail
cd "$(dirname "$0")"
source ./lib.sh

echo "GET $BASE_URL/healthz"
curl -sS -w "\nHTTP %{http_code}\n" "$BASE_URL/healthz"
