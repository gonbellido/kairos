#!/bin/bash
# KAIROS — Production Deploy v2 (with versioning)
set -e
GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "manual")
echo "🚀 Deploying KAIROS ($GIT_SHA) to production..."

ssh -i ~/.ssh/id_rsa root@95.217.217.222 << 'REMOTE'
cd /opt/kairos
echo "Building..."
docker compose build app --no-cache 2>&1 | tail -3

echo "Recreating app..."
docker compose up -d --force-recreate app

echo "Running migrations..."
sleep 5
docker compose exec -T app sh -c "cd /app/kairos/db && alembic upgrade head" 2>&1 | tail -3

echo "Health check..."
sleep 8
curl -sf http://localhost:8000/health > /dev/null && echo "✅ Deploy OK" || echo "❌ Health check failed"

echo "Containers:"
docker compose ps
REMOTE
