FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml setup.cfg ./
COPY kairos/ /app/kairos/
COPY profiles/ /app/profiles/
COPY obsidian_templates/ /app/obsidian_templates/
COPY main.py /app/main.py

RUN pip install --no-cache-dir -e ".[voice]"

RUN addgroup --system appuser && \
    adduser --system --ingroup appuser appuser
RUN chown -R appuser:appuser /app
USER appuser

CMD ["python", "-m", "kairos.engine.voice_agent", "start"]
