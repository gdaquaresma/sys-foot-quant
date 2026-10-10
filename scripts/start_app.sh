#!/usr/bin/env bash
# Lance le backend (FastAPI, lecture seule) et le frontend (Vite) de
# sys-foot-quant en local, puis ouvre le navigateur. Arreter avec Ctrl+C
# (les deux serveurs sont arretes proprement). Usage : ./scripts/start_app.sh
# ou "make run" depuis la racine du depot.
set -euo pipefail

cd "$(dirname "$0")/.."

BACKEND_PORT=8000
FRONTEND_PORT=5173
URL="http://127.0.0.1:${FRONTEND_PORT}"

cleanup() {
    echo ""
    echo "Arret des serveurs..."
    [[ -n "${BACKEND_PID:-}" ]] && kill "$BACKEND_PID" 2>/dev/null || true
    [[ -n "${FRONTEND_PID:-}" ]] && kill "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Demarrage du backend (FastAPI, port ${BACKEND_PORT})..."
uv run uvicorn sys_foot_quant.api.app:app --host 127.0.0.1 --port "$BACKEND_PORT" &
BACKEND_PID=$!

echo "Demarrage du frontend (Vite, port ${FRONTEND_PORT})..."
(cd frontend && npm run dev -- --port "$FRONTEND_PORT") &
FRONTEND_PID=$!

sleep 3
echo ""
echo "sys-foot-quant est pret : ${URL}"

if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$URL" >/dev/null 2>&1 || true
elif command -v open >/dev/null 2>&1; then
    open "$URL" >/dev/null 2>&1 || true
fi

echo "Ctrl+C pour tout arreter."
wait
