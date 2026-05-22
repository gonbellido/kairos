# KAIROS Constitution

## Core Principles

### I. Journey-Driven Coaching
Every feature MUST align with the journey system. Journeys define the coaching flow (phases → agents → prompts). New functionality MUST integrate with or extend the journey engine rather than bypassing it.

### II. Multi-Agent Pipeline
All client interactions flow through the LangGraph pipeline. Changes MUST NOT break the pipeline. New agents MUST be added as LangGraph nodes.

### III. Test-First for Core Logic
Business logic (journey engine, scoring, memory stores, validation) MUST have tests. Tests MUST be written before or alongside implementation.

### IV. 4-Level Memory Architecture
Memory operations MUST respect the layered model: N1 (raw) → N2 (cases) → N3 (patterns) → N4 (executions). No direct writes to higher levels without going through the proper pipeline.

### V. Observable by Default
All pipeline nodes MUST emit timing metrics. Failures MUST be logged with trace_id context.

### VI. Configuration over Hardcoding
Coach behaviors MUST be configurable via YAML profiles or env vars. No hardcoded coach-specific logic in engine code.

### VII. Real-Time Voice First
Voice interactions MUST be first-class citizens, not an afterthought. The LiveKit-based voice pipeline must match the quality and capabilities of the text-based pipeline.

### VIII. Swarm-Oriented Architecture
Multi-agent conversations SHOULD use LangGraph Swarm patterns for specialized agent routing. New agent types SHOULD be added as swarm members, not pipeline extensions.

## Deployment Constraints

- `docker-compose.prod.yml` is the SINGLE source of truth for deployment
- `docker compose` without `-f` is FORBIDDEN
- Auth changes require updating `kairos/api/middleware.py` whitelist
- Python code changes require `docker compose restart app`
- `.env` MUST NOT exist on production
- Volume mounts enable live rsync

## Development Workflow

1. Design via spec (user story → journey mapping → agent behavior)
2. Implement against the journey engine
3. Test with `pytest tests/`
4. Rsync + restart app on server
5. Verify via health endpoint and integration test

**Version**: 1.0.0 | **Ratified**: 2026-05-22 | **Last Amended**: 2026-05-22
