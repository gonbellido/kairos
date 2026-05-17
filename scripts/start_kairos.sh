#!/bin/bash
cd /Users/gbellido/Documents/KAIROS || exit 1

# Source environment and Python
source /Users/gbellido/Documents/KAIROS/.venv/bin/activate

# Read and export .env vars (bypass set -a issues)
export GOOGLE_API_KEY=$(grep '^GOOGLE_API_KEY=' .env | head -1 | cut -d= -f2-)
export LLM_API_KEY=$(grep '^LLM_API_KEY=' .env | head -1 | cut -d= -f2-)
export OPENAI_BASE_URL=$(grep '^OPENAI_BASE_URL=' .env | head -1 | cut -d= -f2-)
export QDRANT_HOST=localhost
export QDRANT_PORT=6333

exec python3 -m uvicorn kairos.api.server:app --host 127.0.0.1 --port 8000
