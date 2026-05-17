.PHONY: install dev seed test lint docker-up docker-down clean

install:
	python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"

dev: install
	@echo "⚡ Run: make docker-up && make seed && make serve"

serve:
	uvicorn kairos.api.server:app --host 127.0.0.1 --port 8000 --reload

docker-up:
	docker compose up -d qdrant postgres
	@echo "⏳ Waiting for Qdrant..."
	@for i in $$(seq 1 30); do curl -sf http://localhost:6333/healthz >/dev/null && echo "✅ Qdrant ready" && break || sleep 1; done

docker-down:
	docker compose down

seed:
	source .venv/bin/activate && python scripts/seed_experience.py --sample

test:
	source .venv/bin/activate && python -m pytest tests/ -v

lint:
	source .venv/bin/activate && ruff check kairos/

bootstrap:
	./scripts/bootstrap.sh

clean:
	rm -rf .venv .pytest_cache .ruff_cache __pycache__
	find . -name "*.pyc" -delete
