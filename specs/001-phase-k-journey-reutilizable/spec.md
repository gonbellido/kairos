# Feature Specification: Fase K — Journey System Reutilizable

**Feature Branch**: `feat/phase-k-journey-reutilizable`

**Created**: 2026-05-22

**Status**: Draft

## User Scenarios

### User Story 1 — Clonar Journey como Template (Priority: P1)

Como admin, quiero duplicar un journey existente (con todas sus fases y agentes) para usarlo como template base y personalizarlo sin partir de cero.

**Independent Test**: Desde el admin panel, click "Duplicar" en un journey → se crea copia exacta con nombre "Copia de [original]".

**Acceptance Scenarios**:
1. **Given** un journey con 3 fases y 5 agentes, **When** hago clic en "Duplicar", **Then** se crea un nuevo journey con los mismos datos y nombre "Copia de [original]"
2. **Given** el journey duplicado, **When** lo edito, **Then** los cambios no afectan al original

---

### User Story 2 — Validación de Esquema JSON en Agentes (Priority: P1)

Como coach, quiero que los agentes validen su output contra un esquema JSON definido, para garantizar que los datos recolectados sean consistentes.

**Independent Test**: Configurar un agente con schema `{name: string, age: number}` → el agente rechaza output que no cumpla el schema.

**Acceptance Scenarios**:
1. **Given** un agente con output_schema definido, **When** el LLM devuelve JSON inválido, **Then** el sistema rechaza y pide corrección
2. **Given** un agente sin output_schema, **When** el LLM responde, **Then** se acepta sin validación

---

### User Story 3 — Transiciones por Tags Genéricas (Priority: P2)

Como arquitecto de journeys, quiero definir transiciones entre fases basadas en tags (no solo orden_index) para crear flujos condicionales.

**Independent Test**: Journey con 2 fases: fase A tag `to_urgent` → fase B. Cliente con flag urgente salta directo a fase B.

**Acceptance Scenarios**:
1. **Given** un journey con tag_mappings, **When** el agente actual devuelve `next_step_tag: "to_phase_3"`, **Then** el sistema salta a la fase mapeada
2. **Given** un journey sin tag_mappings, **When** el agente completa, **Then** avanza por orden_index normal

---

### User Story 4 — Integración RAG con CaseStore (Priority: P2)

Como coach, quiero que los agentes del journey inyecten casos relevantes de memoria (CaseStore) en su prompt, para dar respuestas contextuales basadas en experiencia previa.

**Independent Test**: Crear un case en memora → iniciar journey → el prompt del agente contiene el case relevante.

**Acceptance Scenarios**:
1. **Given** un cliente con sesiones previas, **When** inicia un journey, **Then** los memory_hits se inyectan en el system_prompt
2. **Given** un cliente sin historial, **When** inicia un journey, **Then** el prompt no incluye memory_hits

## Functional Requirements

- **FR-001**: System MUST allow cloning a journey with all phases and agents via a single API call
- **FR-002**: System MUST validate agent output against `output_schema` before storing collected_data
- **FR-003**: System MUST route between phases by tag_mappings when `next_step_tag` is present
- **FR-004**: System MUST inject CaseStore results as context in agent system_prompts
- **FR-005**: System MUST version journeys (MAJOR.MINOR.PATCH) on each modification
- **FR-006**: System MUST support template placeholders (`{{client_name}}`, `{{coach_name}}`) in agent prompts

## Success Criteria

- **SC-001**: Journey cloning completes in <1s for journeys with up to 10 phases
- **SC-002**: JSON schema validation catches 100% of malformed agent outputs
- **SC-003**: Tag-based routing works for up to 20 concurrent clients without state collision
- **SC-004**: RAG injection adds <500ms latency per pipeline invocation
