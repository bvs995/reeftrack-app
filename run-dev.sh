#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"

echo "=========================================================="
echo "  🌊 AquaPulse - Modo Desarrollo (Hot Reload)"
echo "=========================================================="
echo ""

# Iniciar backend FastAPI en segundo plano
echo "🚀 Iniciando Backend FastAPI en http://localhost:8000 ..."
PYTHONPATH=. backend/venv/bin/python3 -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Detener backend al salir con CTRL+C
trap "echo 'Deteniendo servicios...'; kill $BACKEND_PID 2>/dev/null; exit" SIGINT SIGTERM EXIT

# Iniciar frontend Vite
echo "✨ Iniciando Frontend Vite en http://localhost:5173 ..."
cd frontend
npm run dev -- --host 0.0.0.0 --port 5173
