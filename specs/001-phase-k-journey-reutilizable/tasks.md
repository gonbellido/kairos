# Tasks: Fase K — Journey System Reutilizable

**Prerequisites**: `plan.md`, `spec.md`

## Phase 1: Clone Journey (K8 — P1)

**Goal**: Admin puede duplicar cualquier journey con sus fases y agentes

### Tests

- [ ] T001 [US1] Test clone endpoint returns exact copy in `tests/test_journey_engine.py`
- [ ] T002 [US1] Test cloned journey is independent (modifying clone doesn't affect original)

### Implementation

- [ ] T003 [P] [US1] Add `clone_journey(journey_id)` method in `kairos/engine/journey_engine.py`
- [ ] T004 [US1] Add `POST /api/v1/journeys/{id}/clone` endpoint in `kairos/api/routes/web.py`
- [ ] T005 [US1] Add "Duplicar" button in `kairos/web/templates/admin_journeys.html`
- [ ] T006 [US1] Wire clone button to clone endpoint in JS

**Checkpoint**: Admin puede clonar un journey desde la UI

---

## Phase 2: JSON Schema Validation (K3 — P1)

**Goal**: Agentes validan su output contra `output_schema` antes de almacenar

### Tests

- [ ] T007 [US2] Test valid JSON passes validation in `tests/test_journey_engine.py`
- [ ] T008 [US2] Test invalid JSON is rejected with error details

### Implementation

- [ ] T009 [P] [US2] Add `validate_agent_output(schema, output)` to `kairos/engine/journey_engine.py`
- [ ] T010 [US2] Hook validation into response processing in `kairos/agents/nodes/worker.py`
- [ ] T011 [US2] On validation failure: log warning, request LLM correction

**Checkpoint**: Agentes rechazan output inválido y piden corrección

---

## Phase 3: Tag Transitions (K2 — P2)

**Goal**: Journey puede saltar entre fases por tags en vez de solo orden secuencial

### Tests

- [ ] T012 [US3] Test tag jump routes to correct phase
- [ ] T013 [US3] Test fallback to order_index when no tag

### Implementation

- [ ] T014 [US3] Implement tag lookup in `advance_client()` in `kairos/engine/journey_engine.py`
- [ ] T015 [US3] Wire next_step_tag from agent output into routing decision

**Checkpoint**: Journey salta por tags correctamente, con fallback secuencial

---

## Phase 4: RAG + CaseStore (K4 — P2)

**Goal**: Agentes reciben casos relevantes de memoria como contexto en su prompt

### Tests

- [ ] T016 [US4] Test RAG injects cases when `rag_top_k > 0`
- [ ] T017 [US4] Test RAG disabled when `rag_top_k == 0`

### Implementation

- [ ] T018 [P] [US4] Add CaseStore search in `kairos/agents/nodes/retrieve.py`
- [ ] T019 [US4] Inject top-k cases into `compose_agent_prompt()` in `kairos/engine/journey_engine.py`
- [ ] T020 [US4] Add `rag_top_k` config to agent model in `kairos/db/models.py`

**Checkpoint**: Prompts de agentes incluyen casos relevantes de memoria

---

## Phase 5: Template Placeholders (K6 — P2)

**Goal**: System prompts pueden usar `{{client_name}}`, `{{coach_name}}`, etc.

### Tests

- [ ] T021 [K6] Test placeholder resolution with valid data
- [ ] T022 [K6] Test unknown placeholder left as-is

### Implementation

- [ ] T023 [K6] Add placeholder resolution in `compose_agent_prompt()` in `kairos/engine/journey_engine.py`
- [ ] T024 [K6] Resolve from `collected_data` + coach info

**Checkpoint**: Prompts resuelven placeholders correctamente

---

## Phase 6: Journey Versioning (K1 — P3)

**Goal**: Journeys tienen version semver que se auto-incrementa

### Tests

- [ ] T025 [K1] Test version bumps on update
- [ ] T026 [K1] Test initial version is 1.0.0

### Implementation

- [ ] T027 [P] Add version field to JourneyModel in `kairos/db/models.py`
- [ ] T028 [K1] Add migration for version column
- [ ] T029 [K1] Auto-bump on update in `journey_engine.update_journey()`
- [ ] T030 [K1] Show version in admin UI in `kairos/web/templates/admin_journeys.html`

**Checkpoint**: Journeys muestran version y se auto-incrementan

---

## Execution Order

1. Phase 1: Clone (P1) — arrancar ya
2. Phase 2: Schema Validation (P1)
3. Phase 3: Tag Transitions (P2)
4. Phase 4: RAG (P2)
5. Phase 5: Placeholders (P2)
6. Phase 6: Versioning (P3)
