# Guía de Construcción de Journeys — KAIROS F0-F7

> Documento de referencia para diseñar y configurar cualquier journey
> (coaching, comercial, financiero, bioneuro, etc.) usando todas las
> capacidades del motor: tags, guards, fallback, derivación.

---

## 1. Anatomía de un journey

Un journey es un proceso conversacional estructurado en 3 niveles:

```
Journey (objetivo general, tipo, output_schema)
  └── Phase (etapa, orden, objetivo de fase)
        └── Agent (el que conversa: prompt, campos, tags, reglas)
```

Cada nivel tiene configuraciones que el motor usa para enrutar, evaluar y
persistir.

### 1.1 Journey (metadatos)

| Campo | Descripción | Ejemplo |
|---|---|---|
| `name` | Nombre visible en admin | "Coaching Personal" |
| `description` | Qué hace | "Proceso de acompañamiento para desarrollo personal" |
| `objective` | Resultado esperado | "Alcanzar claridad, definir objetivos y ejecutar plan" |
| `profile_type` | Categoría | `coaching`, `comercial`, `financiero`, `bioneuro`, `custom` |
| `output_schema` | Formato JSON esperado del LLM | `{"message":"str","structured":{},"suggested_tags":[],...}` |
| `tag_mappings` | Tags globales del journey (merge con los del agente) | `{"urgent":"fase_urgencia_id"}` |

### 1.2 Phase (fase)

| Campo | Descripción |
|---|---|
| `name` | Nombre visible (ej. "Diagnóstico", "Plan de Acción") |
| `objective` | Qué se debe lograr en esta fase (usado por el evaluador F2) |
| `order_index` | Orden secuencial (0, 1, 2...) |

### 1.3 Agent (agente de conversación)

| Campo | Obligatorio | Descripción |
|---|---|---|
| `name` | Sí | Nombre del agente (ej. "Explorador") |
| `role` | Sí | Rol breve (ej. "Diagnóstico inicial") |
| `goal` | Sí | Objetivo concreto del agente |
| `system_prompt` | **Sí** | Instrucciones completas + formato JSON obligatorio |
| `instructions` | No | Notas adicionales para el LLM |
| `collects_fields` | **Sí** | Lista de campos a recolectar. El evaluador F2 los chequea |
| `allowed_tags` | Sí | Tags que este agente puede emitir para saltar |
| `tag_mappings` | Sí | `{"tag": order_index_destino}` — a dónde salta cada tag |
| `max_turns` | Recomendado | Turnos máximos antes de que el coach deba intervenir |
| `fallback_agent_id` | Opcional | Agente al que derivar si se excede max_turns |
| `output_schema` | Opcional | Schema JSON específico del agente |
| `is_active` | Sí | `true` para activo |

---

## 2. Cómo funciona la navegación

El motor evalúa el avance en este orden **cada turno** (post F0-F4):

```
1. TAGS del agente        → ¿emitió suggested_tags o next_step_tag?
                              Si coincide con allowed_tags y tag_mappings → salta
2. GUARDS del coordinador  → ¿hay transiciones configuradas (F3)?
                              Evalúa por prioridad: turns, field, objective_met
3. PHASE_COMPLETED         → ¿el JSON del LLM marcó phase_completed: true?
                              Si sí → avance lineal (siguiente fase)
4. FALLBACK                → ¿turn_count >= agent.max_turns?
                              Si sí y hay fallback_agent_id → salta a ese agente
5. NADA                    → se queda en el mismo agente, turn_count++
```

**Regla de oro**: el agente NUNCA debe decidir POR SÍ MISMO a dónde saltar.
Solo emite un **tag** y el `tag_mappings` decide el destino.

---

## 3. Formato JSON obligatorio en el system_prompt

Todo agente que recolecta datos debe exigir este formato:

```json
{
  "message": "texto que lee el cliente (nunca vacío)",
  "structured": {
    "phase_completed": false,
    "required_fields": {
      "campo1": "valor",
      "campo2": "valor"
    }
  },
  "suggested_tags": [],
  "next_step_tag": "to_siguiente_fase",
  "confidence": 0.0,
  "escalation_flag": false
}
```

**Template para el system_prompt:**

```
Eres un coach de [TIPO] en la fase [NOMBRE]. [OBJETIVO].

[Instrucciones específicas del agente]

Responde SIEMPRE en JSON:
{"message":"tu respuesta al cliente",
 "structured":{"phase_completed":false,"required_fields":{"campo":"valor"}},
 "next_step_tag":null,"escalation_flag":false}

Cuando tengas TODOS los campos con valores reales:
- phase_completed: true
- next_step_tag: "to_siguiente_fase"
```

---

## 4. Patrones de diseño

### 4.1 Intake lineal (recolección progresiva)

El caso más simple: fases secuenciales donde cada agente recolecta sus campos
y avanza.

```
Fase 1 (Diagnóstico) → tag:to_plan → Fase 2 (Plan) → tag:to_action → Fase 3 (Acción)
```

**Configuración:**
- `collects_fields`: los campos de esa fase
- `allowed_tags`: `["to_plan"]`, `["to_action"]`, etc.
- `tag_mappings`: `{"to_plan": 1}`, `{"to_action": 2}`, etc.
- `max_turns`: 5-8 (según complejidad)

### 4.2 Bifurcación condicional (rutas alternativas)

Cuando el camino depende de lo que diga el cliente. El agente emite tags
distintos según la respuesta.

```
                 ┌─ tag:to_urgent ──→ Fase Urgencia
Fase Diagnóstico ─┤
                 └─ tag:to_normal ──→ Fase Normal
```

**Configuración:**
- `allowed_tags`: `["to_urgent", "to_normal"]`
- `tag_mappings`: `{"to_urgent": 2, "to_normal": 3}` (order_index distintos)

El system_prompt debe indicar claramente cuándo emitir cada tag:
"Si el síntoma es físico → suggested_tags: ['to_urgent']. Si es emocional → ['to_normal']."

### 4.3 Salto por guard (transiciones F3)

Cuando la decisión no depende del agente sino de **datos objetivos** del
cliente. Se configura desde el admin → botón "Transiciones".

| Guard | Cuándo usarlo | Ejemplo |
|---|---|---|
| `turns` | Tras N interacciones en una fase | Si lleva 5 turnos sin avanzar → derivar a "Reencuadre" |
| `field` | Cuando un campo ya está presente | Si `email` ya existe → saltar fase de recolectar email |
| `objective_met` | Cuando el evaluador F2 dice que el objetivo se cumplió | Confianza ≥ 0.8 → avanzar |

**Ejemplo de transición:**
```json
{
  "from_phase_id": "id_fase_diagnostico",
  "to_phase_id": "id_fase_urgencia",
  "condition": {"type": "turns", "min": 5},
  "priority": 10
}
```

### 4.4 Derivación entre journeys (F5)

Cuando un proceso deriva naturalmente a otro distinto. El cliente conserva
su `shared_profile` (nombre, datos, historial).

**Ejemplo:** journey de "Coaching Personal" detecta un problema financiero
crítico → deriva a "Planificación Financiera".

**Configuración:** en el admin, al crear una transición, elegir como destino
otro journey del dropdown.

### 4.5 Cierre del journey

Dos formas de terminar:
1. **`next_step_tag: "journey_complete"`** con `tag_mappings: {"journey_complete": 99}` — completa el journey.
2. **Transición con destino `__complete__`** — completa vía guard.

---

## 5. Calibración de `max_turns`

| Tipo de fase | max_turns | Justificación |
|---|---|---|
| Intake simple (nombre, email) | 5-6 | Campos concretos, fáciles de dar |
| Exploración emocional (hachazo, miedos) | 8-12 | El cliente puede bloquearse |
| Tareas creativas (perfil, atributos) | 10-12 | Requiere reflexión |
| Confirmación / administrativo | 3-4 | Es solo validar |
| Cierre | 3 | Resumen rápido |

Si `max_turns = 0` → sin límite (no recomendado, el agente puede estancarse
para siempre).

---

## 6. Checklist para validar un journey antes de activarlo

- [ ] Cada fase tiene `objective` concreto y medible.
- [ ] Cada agente tiene `system_prompt` con **formato JSON explícito**.
- [ ] Cada agente tiene `collects_fields` (los campos que debe obtener).
- [ ] Cada agente tiene `allowed_tags` con al menos 1 tag de avance.
- [ ] Cada tag en `allowed_tags` tiene entrada en `tag_mappings` apuntando al `order_index` correcto.
- [ ] Los `max_turns` están calibrados según el tipo de fase.
- [ ] El último agente tiene `journey_complete` en `allowed_tags` y `tag_mappings: {"journey_complete": 99}`.
- [ ] No hay agentes con `collects_fields` vacío sin un plan alternativo (guards o derivación).
- [ ] Se corrió el **Test** del journey (botón "Test" en admin) y todos los agentes pasan.
- [ ] Las transiciones con guards (F3) están creadas para fases que pueden estancarse.

---

## 7. Ejemplo mínimo: "Coaching Express" (3 fases)

```yaml
journey:
  name: "Coaching Express"
  profile_type: "coaching"
  objective: "Definir un objetivo SMART en 3 pasos"
  phases:
    - name: "1. Contexto"
      objective: "Entender la situación actual"
      order_index: 1
      agents:
        - name: "Explorador"
          goal: "Obtener situación actual y motivación"
          collects_fields: [situacion, motivacion]
          allowed_tags: [to_objetivo]
          tag_mappings: {to_objetivo: 2}
          max_turns: 6
          system_prompt: |
            Eres un coach en fase Contexto. Preguntá:
            1. ¿Cuál es tu situación actual?
            2. ¿Qué te motiva a cambiarla?
            Responde JSON con required_fields: situacion, motivacion.
            Al completar: phase_completed:true, next_step_tag:"to_objetivo".

    - name: "2. Objetivo"
      objective: "Definir un objetivo SMART"
      order_index: 2
      agents:
        - name: "Enfocador"
          goal: "Convertir la motivación en objetivo concreto"
          collects_fields: [objetivo_smart, criterio_exito, plazo]
          allowed_tags: [to_cierre]
          tag_mappings: {to_cierre: 3}
          max_turns: 8
          system_prompt: |
            Eres un coach en fase Objetivo. Ayudá a definir un objetivo SMART.
            Responde JSON con required_fields: objetivo_smart, criterio_exito, plazo.
            Al completar: phase_completed:true, next_step_tag:"to_cierre".

    - name: "3. Cierre"
      objective: "Resumir y empoderar"
      order_index: 3
      agents:
        - name: "Cerrador"
          goal: "Resumir el objetivo y cerrar"
          collects_fields: []
          allowed_tags: [journey_complete]
          tag_mappings: {journey_complete: 99}
          max_turns: 3
          system_prompt: |
            Eres un coach en fase Cierre. Resumí el objetivo definido.
            Felicitá y cerrá. Responde JSON con phase_completed:true,
            next_step_tag:"journey_complete".
```

---

## 8. Journey Architect — prompt para IA generadora

Para pedirle al Journey Architect que genere un journey, usar este template:

```
Creá un journey de tipo [coaching|comercial|financiero|bioneuro|custom]
llamado "[NOMBRE]" con objetivo "[OBJETIVO]".

El journey debe tener [N] fases. Cada fase un agente.
Cada agente debe incluir:
- collects_fields (lista de campos a recolectar)
- allowed_tags y tag_mappings para navegación
- max_turns calibrado según la complejidad de la fase
- system_prompt con formato JSON obligatorio

El formato de navegación es secuencial con tags.
La última fase debe cerrar con journey_complete.
```

---

## 9. Archivos de referencia

| Archivo | Contenido |
|---|---|
| `kairos/engine/journey_engine.py` | Templates DEFAULT_JOURNEYS (ejemplos reales) |
| `kairos/db/models.py` | Modelos: Journey, Phase, Agent, Transition |
| `docs/JOURNEY_ENGINE_ARCHITECTURE.md` | Arquitectura completa del motor F0-F7 |
| `docs/BIONEURO_12_PASOS.md` | Ejemplo completo de un journey terapéutico |
