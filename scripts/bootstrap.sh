#!/usr/bin/env bash
set -euo pipefail

echo "╔════════════════════════════════════════════╗"
echo "║     KAIROS — Bootstrap MVP                ║"
echo "╚════════════════════════════════════════════╝"

# ── 1. Check prerequisites ──────────────────────────────────────────
echo ""
echo "🔍 Checking prerequisites..."

command -v python3 >/dev/null 2>&1 || { echo "❌ python3 required"; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "❌ docker required"; exit 1; }
command -v docker compose >/dev/null 2>&1 || docker --version | grep -q compose || { echo "❌ docker compose required"; exit 1; }

echo "   ✅ python3 $(python3 --version | cut -d' ' -f2)"
echo "   ✅ docker $(docker --version | cut -d' ' -f3 | tr -d ',')"
echo "   ✅ docker compose"

# ── 2. Setup .env ───────────────────────────────────────────────────
echo ""
echo "🔧 Setting up environment..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "   ✅ Created .env from .env.example"
    echo "   ⚠️  Edit .env to add your LLM_API_KEY"
else
    echo "   ✅ .env already exists"
fi

# Source .env for this script
set -a; source .env 2>/dev/null || true; set +a

# ── 3. Python virtual environment ───────────────────────────────────
echo ""
echo "🐍 Setting up Python environment..."
if [ ! -d .venv ]; then
    python3 -m venv .venv
    echo "   ✅ Created .venv"
fi
source .venv/bin/activate
pip install -q -e ".[dev]" 2>&1 | tail -1
echo "   ✅ Dependencies installed"

# ── 4. Start infrastructure ─────────────────────────────────────────
echo ""
echo "🐳 Starting infrastructure (Qdrant + PostgreSQL)..."
docker compose up -d qdrant postgres 2>&1 | tail -3

# Wait for Qdrant
echo "   ⏳ Waiting for Qdrant..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:6333/healthz >/dev/null 2>&1; then
        echo "   ✅ Qdrant ready"
        break
    fi
    sleep 1
done

# Wait for PostgreSQL
echo "   ⏳ Waiting for PostgreSQL..."
for i in $(seq 1 30); do
    if docker compose exec postgres pg_isready -U kairos >/dev/null 2>&1; then
        echo "   ✅ PostgreSQL ready"
        break
    fi
    sleep 1
done

# ── 5. Database setup ───────────────────────────────────────────────
echo ""
echo "🗄️  Setting up database..."
source .venv/bin/activate
cd kairos/db
if alembic upgrade head 2>&1 | grep -q "No migrations"; then
    alembic revision --autogenerate -m "initial_schema" 2>&1 | tail -1
    alembic upgrade head 2>&1 | tail -1
fi
cd - >/dev/null
echo "   ✅ Database migrations applied"

# ── 6. Seed data ────────────────────────────────────────────────────
echo ""
echo "🌱 Seeding sample data..."
source .venv/bin/activate
python scripts/seed_experience.py --sample 2>&1 | tail -3
echo "   ✅ Sample experiences loaded"

# ── 7. Start server ─────────────────────────────────────────────────
echo ""
echo "🚀 Starting KAIROS server..."
echo ""
echo "   ╔══════════════════════════════════════════════╗"
echo "   ║                                              ║"
echo "   ║   KAIROS running at:                         ║"
echo "   ║   📊 Coach UI : http://localhost:8000/coach  ║"
echo "   ║   📋 API docs : http://localhost:8000/docs   ║"
echo "   ║   💬 Chat API : POST /api/v1/chat            ║"
echo "   ║   ❤️  Health  : http://localhost:8000/health  ║"
echo "   ║                                              ║"
echo "   ╚══════════════════════════════════════════════╝"
echo ""

uvicorn kairos.api.server:app --host 0.0.0.0 --port 8000 --reload
