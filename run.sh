#!/bin/bash
# Arranca KAIROS + Qdrant. Ejecutar en una TERMINAL NUEVA.
#   cd ~/Documents/KAIROS && bash run.sh

set -e

echo "🚀 KAIROS — Iniciando..."

# 1. Asegurar Qdrant
if ! curl -sf http://localhost:6333/healthz > /dev/null 2>&1; then
    echo "📦 Levantando Qdrant..."
    docker compose up -d qdrant
    sleep 3
fi

# 2. Activar entorno
source .venv/bin/activate

# 3. Arrancar servidor (queda en foreground)
echo "🌐 Servidor: http://127.0.0.1:8000"
echo "📋 Dashboard: http://127.0.0.1:8000/coach"
echo ""
uvicorn kairos.api.server:app --host 127.0.0.1 --port 8000 --reload
