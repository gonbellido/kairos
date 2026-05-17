#!/bin/bash
# KAIROS Server — haz doble click para arrancar
# Las keys se cargan desde .env automáticamente

cd "$(dirname "$0")"
source .venv/bin/activate

# Exportar variables del .env
export $(grep -v '^\s*#' .env | grep -v '^\s*$' | xargs)

echo "=========================================="
echo "  KAIROS — Servidor de Coaching IA"
echo "=========================================="
echo ""
echo "  Dashboard: http://127.0.0.1:8000/coach"
echo "  API Docs:  http://127.0.0.1:8000/docs"
echo "  Health:    http://127.0.0.1:8000/health"
echo ""
echo "  Ctrl+C para detener"
echo "=========================================="
echo ""

uvicorn kairos.api.server:app --host 127.0.0.1 --port 8000

echo ""
echo "Servidor detenido."
read -p "Presiona Enter para cerrar..."
