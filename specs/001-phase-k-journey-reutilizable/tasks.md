# Tasks: Fase K — Journey System Reutilizable

**Status**: 8/10 completed ✅

**Prerequisites**: `plan.md`, `spec.md`

## Phase 1: Clone Journey (K8 — P1) ✅

**Goal**: Admin puede duplicar cualquier journey con sus fases y agentes

### Tests ✅

- [x] T001 Test clone endpoint returns exact copy in `tests/test_journey_integration.py`
- [x] T002 Test cloned journey is independent

### Implementation ✅

- [x] T003 Add `clone_journey(journey_id)` method in `kairos/engine/journey_engine.py`
- [x] T004 Add `POST /api/v1/journeys/{id}/clone` endpoint in `kairos/api/routes/web.py`
- [x] T005 Add "Duplicar" button in `kairos/web/templates/admin_journeys.html`
- [x] T006 Wire clone button to clone endpoint in JS

---

## Phase 2: JSON Schema Validation (K3 — P1) ✅

**Goal**: Agentes validan su output contra `output_schema` antes de almacenar

### Tests ✅

- [x] T007 Test valid JSON passes validation in `tests/test_journey_architect.py`
- [x] T008 Test invalid JSON is rejected with error details

### Implementation ✅

- [x] T009 Add `validate_agent_output(schema, output)` function
- [x] T010 Hook validation into response processing in `kairos/agents/nodes/worker.py`
- [x] T011 On validation failure: log warning

---

## Phase 3: Tag Transitions (K2 — P2) ✅

**Goal**: Journey puede saltar entre fases por tags en vez de solo orden secuencial

### Tests ✅

- [x] T012 Test tag jump routes to correct phase
- [x] T013 Test fallback to order_index when no tag

### Implementation ✅

- [x] T014 Implement tag lookup + phase resolution in `validate_and_advance()`
- [x] T015 Wire next_step_tag from agent output into routing + merge agent/journey tag_mappings

---

## Phase 4: RAG + CaseStore (K4 — P2) ✅

**Goal**: Agentes reciben casos relevantes de memoria como contexto en su prompt

### Implementation ✅

- [x] T018 Add CaseStore search in `compose_agent_prompt()`
- [x] T019 Inject top-k cases with score > 0.5 into prompt
- [x] T020 Configurable via `rag_top_k` on agent (0 = disabled)
- [x] Wiring: `journey_inject_node` passes `case_store` + `journey_engine._case_store` set in `server.py`

---

## Phase 5: Template Placeholders (K6 — P2) ✅

**Goal**: System prompts pueden usar `{{client_name}}`, `{{coach_name}}`, etc.

### Implementation ✅

- [x] T023 Add placeholder resolution in `compose_agent_prompt()`: `{{step_title}}`, `{{step_objective}}`, `{{agent_name}}`, `{{journey_name}}`, `{{coach_name}}`, `{{client_name}}`, `{{collected.*}}`
- [x] T024 Resolve from `collected_data` + shared profile

---

## Phase 6: Journey Versioning (K1 — P3) ✅

**Goal**: Journeys tienen version que se auto-incrementa

### Implementation ✅

- [x] T027 Version field already exists in `JourneyModel` (`Column(Integer, default=1)`)
- [x] T029 Auto-bump (+1) on update in `journey_engine.update_journey()`
- [x] T030 Show version badge (`v1`, `v2`, ...) in admin UI

---

## Phase K5: Imprint-to-Text ✅

**Goal**: Traducir valores numéricos de impronta a reglas de comportamiento en lenguaje natural

### Implementation ✅

- [x] Inject `ImprintMapper().map(impronta)` into prompt as `## Estilo de coaching` section
- [x] Accept `coach_imprint` param in `compose_agent_prompt()`
- [x] Pass `coach_imprint` from state in `journey_inject_node`

---

## Phase K9: Monitor Improvements ✅

**Goal**: Tracing de journey agents en el monitor

### Implementation ✅

- [x] Add `trace_journey()` + `get_journey_traces()` in `journey_agent.py`
- [x] Trace `prompt_composed` and `response_processed` events
- [x] Show journey traces in `/admin/monitor` traces tab

---

## Remaining

- [ ] K10: Integration Tests — tests end-to-end del sistema de journeys
