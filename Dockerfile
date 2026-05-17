FROM python:3.13-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml setup.cfg ./
COPY kairos/ /app/kairos/
COPY profiles/ /app/profiles/
COPY obsidian_templates/ /app/obsidian_templates/
COPY main.py /app/main.py

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir ".[dev]"


FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV KAIROS_ENV=production

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev curl && \
    rm -rf /var/lib/apt/lists/*

RUN addgroup --system appuser && \
    adduser --system --ingroup appuser appuser

COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app/ /app/

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -sf http://localhost:8000/health || exit 1

CMD ["uvicorn", "kairos.api.server:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--loop", "uvloop", \
     "--log-level", "info"]
