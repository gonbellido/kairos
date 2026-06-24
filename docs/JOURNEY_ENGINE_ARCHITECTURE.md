# KAIROS — Arquitectura del Journey Engine

> Documento de referencia. Estado actual + arquitectura objetivo.
> Creado: 2026-06-24 · Última actualización: 2026-06-24

Este documento existe para tener una referencia estable del diseño del motor de
journeys: qué hay hoy, qué falta, y hacia dónde vamos. Se actualiza cuando
cambie la arquitectura, no en cada commit.

---

## 1. Resumen ejecutivo

El sistema actual **sí** tiene una jerarquía de datos (Journey → Phase → Agent),
**sí** tiene transiciones no-lineales básicas por tags, y **sí** tiene una memoria
compartida entre journeys. No es "solo un conjunto de prompts planos".

Sin embargo, le falta lo esencial para ser un sistema multi-agente de verdad:

1. **No hay coordinador.** Cada agente de contenido decide su propio avance
   auto-reportándose en JSON. Frágil: si el JSON falla, no avanza.
2. **No hay condicionales reales** (por nº de interacciones, por campo faltante,
   por score). El avance es binario.
3. **El `objective` es decorativo**: se inyecta como texto pero nada evalúa si se
   cumplió.
4. **Los agentes no se comunican**: comparten una pizarra pasiva, no se invocan.
5. **No hay derivación journey → journey.**
6. **La lógica de avance está duplicada e inconsistente** entre los distintos
   caminos de ejecución (ver §3).
7. **Deuda técnica:** existen dos engines (`journey_engine.py` v1 en producción y
   `journey_engine_v2.py` que es código muerto).

---

## 2. Estado actual — Modelo de datos

Definido en `kairos/db/models.py`.

| Tabla / Modelo | Línea | Rol |
|---|---|---|
| `JourneyModel` | `models.py:81` | Journey: `objective`, `tag_mappings`, `version`, `channel` (text/voice/both), `status` |
| `JourneyPhaseModel` | `models.py:98` | Fase: `order_index`, `objective`, `completion_criteria` (texto, no evaluado) |
| `JourneyAgentModel` | `models.py:112` | Agente: `system_prompt`, `goal`, `collects_fields`, `allowed_tags`, `tag_mappings`, `output_schema` |
| `ClientJourneyModel` | `models.py:132` | Estado del cliente: `current_phase_id`, `current_agent_id`, `collected_data`, `progress_pct` |
| `ClientSharedProfileModel` | `models.py:152` | Memoria cross-journey: `profile_data`, `goals_data`, `insights_data`, `blockers_data`, `conversation_summary`, `risk_flags_data` |
| `JourneyEventModel` | `models.py:170` | Log de eventos: `journey_started`, `phase_advanced`, `tag_jump`, `data_collected` |

Jerarquía de datos real:

```
Journey (objective, tag_mappings)
  └── Phase (order_index, objective, completion_criteria)
        └── Agent (system_prompt, goal, collects_fields, allowed_tags, tag_mappings)

ClientJourney  → estado del cliente (puntero a phase/agent actual + collected_data)
ClientSharedProfile → pizarra/memoria persistente del cliente entre journeys
JourneyEvent   → auditoría
```

---

## 3. Estado actual — Flujo de ejecución (y su inconsistencia)

Hay **tres caminos distintos** que avanzan el journey, y **no coinciden**:

### Camino A — Fast path (`kairos/paths/fast_path.py`)
- Compone prompt: `compose_agent_prompt()` (`fast_path.py:48`).
- Avanza por **conteo de campos**: si se recolectaron `>= threshold` campos
  (`min(len(collects_fields), 5)`), llama `advance_client()` **lineal**
  (`fast_path.py:103-118`).
- **No usa tags.** Avance puramente secuencial por `order_index`.

### Camino B — Nodo del grafo (`kairos/agents/nodes/journey_agent.py`)
- `journey_inject_node` compone el prompt (`journey_agent.py:61`).
- `journey_advance_node` llama `validate_and_advance()` (`journey_agent.py:123`),
  que **sí** procesa tags y saltos no-lineales.

### Camino C — Chat/Stream directos (`api/routes/chat.py:92,115`, `stream.py:82,175`)
- También usan `compose_agent_prompt()` + `validate_and_advance()`.

> **Problema:** el Camino A (fast_path) avanza por heurística de conteo y nunca
> dispara tags; los Caminos B/C avanzan por tags + `phase_completed`. El mismo
> journey se comporta distinto según por dónde entre la petición. Esto debe
> unificarse bajo el coordinador.

### Lógica de transición (motor v1: `kairos/engine/journey_engine.py`)

- **`compose_agent_prompt()`** (`journey_engine.py:596`): toma el `system_prompt`
  del agente actual, resuelve placeholders (`{{client_name}}`, `{{collected.*}}`,
  `{{step_objective}}`...), inyecta datos recolectados, estado, RAG
  (`memory_hits` + `CaseStore`), reglas de impronta, y bloque de "retomada de
  sesión" si pasaron >6h (K7, `journey_engine.py:620`).
- **`validate_and_advance()`** (`journey_engine.py:749`): parsea el JSON del LLM,
  extrae `collected_data`/`required_fields`, guarda en `shared_profile`, y aplica
  transición por tags (`suggested_tags` ∩ `allowed_tags` → `tag_mappings` →
  `_jump_to_step`). Si no hubo tag pero sí `phase_completed`, hace `advance_client`
  lineal.
- **`_resolve_next_phase` / `_jump_to_step`** (`journey_engine.py:883`): el salto
  es `tag → order_index/phase_id`. `target == 99` = journey completo.

**Quién decide el avance hoy:** el propio agente de contenido, vía el JSON que
emite. No hay árbitro externo.

---

## 4. Lo que SÍ funciona (no reconstruir)

- Jerarquía Journey/Phase/Agent (§2).
- Transición no-lineal por tags (ej. Bioneuro paso 2 bifurca MCb→paso3 vs
  MCn→paso5, `journey_engine.py:130`).
- Memoria compartida cross-journey: al asignar journey nuevo se pre-puebla
  `collected_data` desde el `shared_profile` previo (`journey_engine.py:404-412`).
- `save_collected()` escribe en `client_journeys` + `shared_profiles` y normaliza
  `vital_fields` (`journey_engine.py:910`).
- RAG inyectado al prompt: `coach_kb` + `session_history` + `CaseStore`
  (`journey_engine.py:709-741`).
- Auditoría vía `JourneyEvent` + traza en memoria `get_journey_traces()`
  (`journey_agent.py:11-24`).

---

## 5. Gaps (lo que falta)

| # | Gap | Evidencia |
|---|---|---|
| G1 | **Sin coordinador.** El agente de contenido decide su propio avance. | `journey_engine.py:749` |
| G2 | **Sin condicionales por nº de interacciones / loop / fallback.** No hay contador de turnos por agente ni política de escape. | No existe |
| G3 | **`objective`/`completion_criteria` decorativos.** No hay evaluador de objetivo. | `models.py:106` |
| G4 | **Avance frágil por JSON.** "JSON parse FAILED → no advancement". | `journey_engine.py:828` |
| G5 | **Lógica de avance duplicada e inconsistente** (conteo vs tags). | `fast_path.py:103` vs `journey_agent.py:123` |
| G6 | **Sin comunicación agente↔agente.** Pizarra pasiva, no colaboración. | — |
| G7 | **Sin derivación journey→journey condicional.** | — |
| G8 | **Memoria accesible solo por similitud (RAG), no por condicional explícito.** | `journey_engine.py:709` |
| G9 | **Dos engines; v2 es código muerto.** Confunde y duplica. | `journey_engine_v2.py` no referenciado en flujo real |

---

## 6. Arquitectura objetivo

### 6.1 Componentes

```
                 ┌───────────────────────────────────────────┐
                 │              COORDINADOR                   │
                 │  (meta-agente / orquestador de objetivos)  │
                 │                                            │
                 │  1. evalúa el objetivo de la fase actual   │
                 │  2. cuenta turnos / detecta estancamiento  │
                 │  3. evalúa guards (condicionales)          │
                 │  4. decide transición (avanzar/saltar/     │
                 │     reformular/derivar a otro journey)     │
                 └─────────────────┬──────────────────────────┘
                                   │ lee/escribe
                       ┌───────────▼────────────┐
                       │      BLACKBOARD         │
                       │ collected_data +        │
                       │ shared_profile + tags + │
                       │ turn_count + objetivos  │
                       └───────────┬────────────┘
        ┌──────────────┬───────────┼───────────┬──────────────┐
   Subagente A     Subagente B  Subagente C  ...            (por objetivo)
   (un objetivo)   (un objetivo)
```

Diferencia clave con hoy: el **coordinador** es quien decide la transición,
**no** el agente de contenido. El agente de contenido solo conversa y propone;
el coordinador observa, evalúa el objetivo y enruta.

### 6.2 Tipos de transición que debe soportar

1. **Lineal** — siguiente `order_index` (ya existe).
2. **Por tag** — salto declarado por el agente (ya existe).
3. **Por guard/condicional** (NUEVO) — expresión evaluable sobre el blackboard:
   - `turn_count > N` → derivar / reformular.
   - `campo X faltante tras N turnos` → agente de rescate.
   - `score_objetivo < umbral` → no avanzar.
   - `risk_flag presente` → escalar / journey de crisis.
4. **Journey → Journey** (NUEVO) — si el coordinador detecta un objetivo fuera
   del journey actual, deriva a otro journey conservando el `shared_profile`.

### 6.3 Evaluador de objetivo (NUEVO)

Para cada fase, el coordinador evalúa si el objetivo se cumplió. Estrategias
(combinables):
- **Determinista**: todos los `collects_fields` presentes y válidos.
- **Semántica (LLM-judge)**: un prompt corto que recibe `objective` +
  transcript reciente y devuelve `{cumplido: bool, confianza: float, faltante: [...]}`.
- **Híbrida**: determinista primero; LLM-judge solo si hay ambigüedad.

---

## 7. Modelo de datos propuesto

Cambios mínimos sobre el esquema actual (migración aditiva, sin romper v1):

### 7.1 `JourneyAgentModel` (o nueva tabla `journey_transitions`)
- `max_turns` (Integer) — turnos antes de disparar fallback.
- `fallback_agent_id` / `fallback_tag` — a dónde derivar si no se cumple objetivo.
- `objective_eval` (JSON) — config del evaluador: `{mode: deterministic|llm|hybrid, threshold}`.

### 7.2 Nueva tabla `JourneyTransitionModel` (grafo explícito)
Reemplaza/complementa `tag_mappings` con condiciones evaluables:

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | String | PK |
| `journey_id` | String | FK |
| `from_phase_id` | String | origen |
| `to_phase_id` | String / `__complete__` / `journey:<id>` | destino |
| `condition` | JSON | guard: `{type: tag\|turns\|field\|score\|risk, ...}` |
| `priority` | Integer | orden de evaluación |

### 7.3 `ClientJourneyModel`
- `turn_count` (Integer) — turnos en el agente actual (reset al transicionar).
- `objective_state` (JSON) — última evaluación del objetivo por fase.

### 7.4 Histórico accesible por condicional (G8)
- Mantener `conversation_summary` + RAG, pero exponer un acceso por clave:
  `shared_profile.profile_data[...]` ya sirve; añadir índice de eventos
  consultable por el coordinador (`JourneyEvent` ya existe, falta API de query).

---

## 8. Flujo del coordinador (pseudocódigo objetivo)

```python
async def coordinate(client_id, message):
    cj = get_client_journey(client_id)
    agent = current_agent(cj)

    # 1. El subagente conversa (genera respuesta + extrae datos)
    response = await run_agent(agent, message, blackboard=cj)
    save_collected(client_id, response.collected_data)
    increment_turn(client_id)

    # 2. El coordinador evalúa el objetivo (NO el agente)
    objective = evaluate_objective(agent, cj)   # determinista | llm | híbrido

    # 3. Resolver transición por prioridad de guards
    for t in transitions(cj.journey_id, from_phase=cj.current_phase_id):
        if guard_satisfied(t.condition, blackboard=cj, objective=objective):
            return apply_transition(client_id, t)   # avanzar/saltar/derivar/completar

    # 4. Fallback por estancamiento
    if cj.turn_count >= agent.max_turns and not objective.cumplido:
        return derive_to(agent.fallback_agent_id or "rescue", client_id)

    # 5. Si nada se cumple, permanecer en el agente actual
    return stay(response)
```

---

## 9. Plan de implementación por fases

| Fase | Entregable | Depende de |
|---|---|---|
| **F0** | Eliminar `journey_engine_v2.py` (código muerto). Unificar avance: fast_path debe usar el mismo `validate_and_advance` que el grafo (G5). | — |
| **F1** | Añadir `turn_count` + `objective_state` a `ClientJourneyModel` (migración aditiva). | F0 |
| **F2** | Evaluador de objetivo determinista (campos completos) + LLM-judge opcional. | F1 |
| **F3** | Tabla `JourneyTransitionModel` con guards; coordinador evalúa transiciones por prioridad. Mantener compat con `tag_mappings`. | F2 |
| **F4** | Política de fallback por `max_turns` → agente de rescate / reformulación. | F3 |
| **F5** | Derivación journey→journey conservando `shared_profile`. | F3 |
| **F6** | UI admin del editor de journeys (ver §11): editor visual de condicionales/derivaciones + loop test→mejora + monitor del coordinador. | F3 |
| **F7** | Tests de integración del coordinador (lineal, salto por tag, guard por turnos, fallback, derivación). | F3-F5 |

---

## 10. Decisiones abiertas

1. **¿`JourneyTransitionModel` nueva tabla, o extender `tag_mappings` a JSON con
   condiciones?** (Tabla = más limpio y consultable; JSON = menos migración.)
2. **¿Evaluador de objetivo por LLM en cada turno (coste/latencia) o solo
   determinista + LLM bajo demanda?** Propuesta: híbrido (determinista por
   defecto, LLM-judge solo en fases marcadas).
3. **¿El coordinador es un módulo nuevo (`kairos/engine/journey_coordinator.py`)
   que envuelve a `JourneyEngine`, o se integra dentro de `validate_and_advance`?**
   Propuesta: módulo nuevo que orquesta, dejando `JourneyEngine` como capa de datos.
4. **Voz vs texto:** el coordinador debe ser agnóstico al canal (el voice agent
   y el chat deben enrutar por el mismo coordinador).

---

## 11. UI/UX objetivo del editor de journeys

El coach debe poder **diseñar y mejorar su journey sin tocar JSON ni código**.
Hoy el editor (`admin_journeys.html`) deja editar tags y schema como **JSON crudo
en un textarea** (`a-tags`, `a-schema` en `admin_journeys.html:156-157`), no hay
editor de `tag_mappings`/condicionales, y el tester (`admin_journey_test.html`)
está **desconectado** del editor. Hay que cerrar esa brecha.

### 11.1 Estado actual de la UI
- `admin_journeys.html`: CRUD de journey/fase/agente vía modales. Agente edita
  `name, role, goal, system_prompt, instructions, allowed_tags (JSON), output_schema (JSON)`.
  Panel lateral "architect" (asistente LLM) para generar journeys.
- `admin_journey_test.html`: simula chat con el cliente, muestra `collects_fields`
  y diagnóstico, pero **no propone cambios aplicables** al journey.
- **Falta:** editor de transiciones/derivaciones, editor de condicionales,
  visión de grafo, y el puente test→mejora.

### 11.2 Capacidades objetivo

1. **Editor visual de condicionales (guards) sin JSON.**
   Constructor tipo formulario: `SI [campo/turnos/score/tag/risk] [operador]
   [valor] ENTONCES [avanzar / saltar a fase X / derivar a journey Y / reformular]`.
   Genera el `JourneyTransitionModel` por debajo (§7.2).

2. **Editor de derivaciones journey→journey.**
   Selector "derivar a otro journey" como destino de una transición, conservando
   el `shared_profile`.

3. **Vista de grafo del journey.**
   Diagrama de fases/agentes con las transiciones (lineales, por tag, por guard)
   dibujadas como aristas etiquetadas. Click en una arista = editar su condición.

4. **Loop test → mejora (lo importante para el coach).**
   - El coach lanza el tester sobre el journey.
   - El diagnóstico detecta problemas (campo nunca recolectado, agente que no
     avanza, loop, objetivo no cumplido) usando los `JourneyEvent` + `turn_count`.
   - El sistema **propone cambios concretos y aplicables con 1 click**:
     ajustar `system_prompt`, añadir/editar una condición, mover una derivación.
   - Botón "Aplicar sugerencia" → escribe el cambio en el journey (versionado).
   - Re-test inmediato para validar la mejora (ciclo cerrado).

5. **Versionado visible.**
   Cada ajuste bumpea `Journey.version` (ya existe, `journey_engine.py:256`);
   mostrar historial y permitir revertir.

6. **Monitor del coordinador en vivo.**
   Extender `get_journey_traces()` (`journey_agent.py:23`) para mostrar, por turno:
   objetivo evaluado, guard disparado, transición tomada, turn_count. Así el
   coach entiende *por qué* el journey enrutó como enrutó.

### 11.3 Principio de diseño
Toda capacidad del coordinador (§6) debe ser **configurable desde la UI**: si el
motor soporta un guard nuevo, el editor debe poder construirlo sin JSON. El
modelo de datos (§7) y la UI (§11) evolucionan juntos.

---

## 12. Archivos relevantes (índice rápido)

| Archivo | Rol |
|---|---|
| `kairos/db/models.py` | Modelos de datos del journey |
| `kairos/engine/journey_engine.py` | Motor v1 (producción): CRUD, compose, validate/advance |
| `kairos/engine/journey_engine_v2.py` | Motor v2 (código muerto, a eliminar) |
| `kairos/paths/fast_path.py` | Camino A: avance por conteo |
| `kairos/agents/nodes/journey_agent.py` | Camino B: nodos inject/advance del grafo |
| `kairos/api/routes/chat.py`, `stream.py`, `voice.py` | Caminos de entrada (chat/stream/voz) |
| `kairos/engine/journey_architect/architect.py` | Generador de journeys asistido por LLM |
| `kairos/engine/journey_tester.py` | Simulador de chat para diagnosticar journeys |
| `kairos/engine/vital_fields.py` | Normalización de campos vitales |
