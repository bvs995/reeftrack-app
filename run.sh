#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"

echo "=========================================================="
echo "  🌊 AquaPulse - PWA para Acuarios & Reef Tracking"
echo "=========================================================="
echo ""

# Verificar venv de backend
if [ ! -d "backend/venv" ]; then
    echo "⚙️  Creando entorno virtual de Python..."
    python3 -m venv backend/venv
    backend/venv/bin/pip install -r backend/requirements.txt
fi

# Verificar build de frontend
if [ ! -d "frontend/dist" ]; then
    echo "⚙️  Compilando frontend React PWA..."
    cd frontend
    npm install
    npm run build
    cd ..
fi

echo "🚀 Iniciando servidor FastAPI en http://localhost:8000 ..."
echo "👉 Abre http://localhost:8000 en tu navegador o móvil para usar la PWA."
echo ""
PYTHONPATH=. backend/venv/bin/python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
