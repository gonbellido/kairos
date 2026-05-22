# Implementation Plan: Fase K — Journey System Reutilizable

**Branch**: `feat/phase-k-journey-reutilizable` | **Date**: 2026-05-22 | **Spec**: `specs/001-phase-k-journey-reutilizable/spec.md`

## Summary

Hacer el sistema de journeys reutilizable y data-driven: versionado, validación de esquemas, transiciones por tags, integración RAG con CaseStore, placeholders en prompts, y clonación de journeys.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: FastAPI, SQLAlchemy, Qdrant, LangChain, Pydantic

**Storage**: PostgreSQL (journeys, phases, agents), Qdrant (CaseStore N2)

**Testing**: pytest + pytest-asyncio

**Target Platform**: Linux server (Docker)

## Constitution Check

- ✅ Test-First: New journey engine logic must include tests
- ✅ Journey-Driven: All changes integrate with existing journey engine
- ✅ Observable: New pipeline nodes must emit metrics
- ✅ Configuration: All new behaviors configurable via journey/agent config

## Implementation Phases

### Phase 1 — Clone Journey (K8)
- Add `POST /api/v1/journeys/{id}/clone` endpoint
- Deep-copy journey + phases + agents with new IDs
- UI: "Duplicar" button in admin_journeys.html
- Tests: clone preserves structure, clone is independent from original

### Phase 2 — JSON Schema Validation (K3)
- Add `validate_output(schema, output)` function in journey_engine
- Hook into `compose_agent_prompt` / response processing
- On validation failure: log warning, request correction from LLM
- Tests: valid passes, invalid rejected with clear errors

### Phase 3 — Tag Transitions (K2)
- Implement tag-based routing in `advance_client()`
- If agent returns `next_step_tag`, look up `tag_mappings` → jump to target phase
- If no tag, fall back to `order_index` progression
- Tests: tag jump works, fallback works, missing tag handled

### Phase 4 — RAG + CaseStore (K4)
- Before `compose_agent_prompt`, search CaseStore for relevant cases
- Inject top-k cases into system_prompt as context
- Configurable via agent config: `rag_top_k` (default 0 = disabled)
- Tests: RAG injects cases, disabled RAG adds no context

### Phase 5 — Template Placeholders (K6)
- Replace `{{client_name}}`, `{{coach_name}}`, `{{collected.field}}` in system_prompts
- Resolve from ClientJourney.collected_data + CoachModel
- Tests: placeholders resolve correctly, unknown placeholder left as-is

### Phase 6 — Journey Versioning (K1)
- Add `version` field to JourneyModel (semver: `1.0.0`)
- Auto-bump on update via `update_journey()`
- Show version in admin UI
- Tests: version bumps correctly, initial version is 1.0.0

## Files to Modify

- `kairos/engine/journey_engine.py` — clone, validate, tag routing, RAG, placeholders
- `kairos/api/routes/web.py` — clone endpoint
- `kairos/web/templates/admin_journeys.html` — clone button, version display
- `kairos/agents/nodes/worker.py` — schema validation hook
- `kairos/agents/nodes/retrieve.py` — RAG integration
- `kairos/db/models.py` — journey version field
- `tests/test_journey_engine.py` — new tests

## Sequence

1. Clone Journey (K8) — simplest, UI-only change
2. JSON Schema Validation (K3) — core engine change
3. Tag Transitions (K2) — routing logic
4. RAG + CaseStore (K4) — memory integration
5. Template Placeholders (K6) — prompt injection
6. Journey Versioning (K1) — metadata + UI
