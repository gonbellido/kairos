# Fase K — Journey System Reutilizable

**Objetivo**: Que cualquier coach pueda diseñar y ejecutar su propio procedimiento de acompañamiento sin modificar código.

---

## Principios

1. **Data-driven**: Todo se define en la BD, no en código
2. **Genérico**: Bioneuromoción, Coaching, Ventas, Financiero... mismo motor
3. **Versionado**: Cambios no rompen ejecuciones activas
4. **Auditable**: Cada decisión del motor queda registrada

---

## K1 — Versionado de Journeys

**Qué**: Cada journey, fase, agente y prompt tiene versión. Al editar, se crea una nueva versión. Los clientes activos siguen con la versión que iniciaron.

**Dónde**: `journeys.version`, `journey_phases.version`, `journey_agents.version`

**UI**: En el gestor de journeys, al editar un agente activo → warning "Hay X clientes en este agente. Los cambios solo aplican a nuevas ejecuciones."

**Esfuerzo**: 2h

---

## K2 — Tag-Based Transitions (genérico)

**Qué**: Cada agente define `allowed_tags` (whitelist de tags que acepta) y el journey define `tag_mappings` (tag → step_id). El LLM sugiere `suggested_tags` → Journey Engine valida → ejecuta salto.

**Ejemplo**:
```json
// journey_definition.tag_mappings
{"urgent_followup": "step_5", "skip_to_closure": "step_15"}

// agent step_3.allowed_tags
["urgent_followup", "jump:step=5"]

// LLM output
{"suggested_tags": ["urgent_followup"], "confidence": 0.92}

// Journey Engine: tag "urgent_followup" → step_5 → avanza
```

**Dónde**: `journey_agents.allowed_tags` (JSON array), `journeys.tag_mappings` (JSON object), `advance_client()`

**Esfuerzo**: 2h

---

## K3 — OUTPUT_SCHEMA Validation genérico

**Qué**: Después de cada respuesta del LLM, el sistema valida el JSON contra el schema del agente. Si falla: 1 reintento con guardrails. Si sigue fallando: `escalation_flag=true`.

**Schema definition** (por agente, configurable en UI):
```json
{
  "required_fields": ["message", "structured"],
  "optional_fields": ["evidence", "suggested_tags", "confidence"],
  "structured_schema": {
    "type": "object",
    "properties": {
      "name": {"type": "string"},
      "symptom": {"type": "string"}
    }
  }
}
```

**Dónde**: `journey_agents.output_schema` (JSON), `validate_and_advance()`

**Esfuerzo**: 2h

---

## K4 — RAG/CaseStore integrado al Journey

**Qué**: Antes de componer el prompt, el sistema busca en la memoria de casos (Qdrant) y pasa `memory_hits` al prompt. El formato es genérico.

**Inyección en prompt**:
```
## Memoria de casos relevantes
{% for hit in memory_hits %}
- Case {{hit.id}} (score: {{hit.score}}, outcome: {{hit.outcome}}): {{hit.snippet}}
{% endfor %}

Usa esta información solo como referencia. Si citas, menciona el ID del caso.
```

**Dónde**: `compose_agent_prompt()`, `retrieve_node` (ya existe, integrar)

**Esfuerzo**: 1h

---

## K5 — Imprint → Texto automático

**Qué**: Las variables de impronta (0-1) se convierten en instrucciones textuales antes de inyectarse al prompt. Genérico para cualquier perfil.

**Ejemplo**:
```python
def imprint_to_text(imprint: dict) -> str:
    rules = []
    if imprint.get("directividad", 0.5) > 0.7: rules.append("Sé directo. Da instrucciones claras.")
    elif imprint.get("directividad", 0.5) < 0.3: rules.append("Sé sutil. Pregunta en vez de afirmar.")
    if imprint.get("emocionalidad", 0.5) > 0.7: rules.append("Muestra empatía. Valida emociones.")
    ...
    return "\n".join(rules)
```

**Dónde**: `compose_agent_prompt()`

**Esfuerzo**: 30min

---

## K6 — Prompt Template Store mejorado

**Qué**: El `system_prompt` de cada agente acepta placeholders que se reemplazan en runtime:

```
Eres {{agent_name}}. Estás en el paso {{step_title}}.
Objetivo: {{step_objective}}.

## Perfil del coach
{{imprint_text}}

## Cliente
{{client_snapshot}}

## Memoria
{{memory_hits}}

## OUTPUT_SCHEMA
{{output_schema_instructions}}
```

**Placeholders disponibles** (genéricos):
- `{{agent_name}}`, `{{step_title}}`, `{{step_objective}}`
- `{{client_snapshot}}`, `{{shared_profile}}`
- `{{memory_hits}}`, `{{imprint_text}}`
- `{{output_schema_instructions}}`
- `{{allowed_transitions}}`

**Dónde**: `compose_agent_prompt()`, template en `journey_agents.system_prompt`

**Esfuerzo**: 1h

---

## K7 — 15 Agentes Bioneuromoción como Template

**Qué**: Seedear el journey completo de 15 pasos con sus prompts detallados. Sirve como ejemplo y como template reutilizable.

**Dónde**: `DEFAULT_JOURNEYS["bioneuro_full"]`

**Esfuerzo**: 1h

---

## K8 — Journey Duplicar/Clonar

**Qué**: Un coach puede clonar un journey existente como base para crear el suyo propio.

**UI**: Botón "Clonar" en el gestor de journeys. Crea copia con `coach_id` del coach.

**Esfuerzo**: 1h

---

## K9 — Monitor de Ejecución (mejora)

**Qué**: El monitor actual muestra actividad. Mejorarlo para mostrar:
- Prompt completo enviado al LLM
- JSON de respuesta del LLM
- Resultado de la validación (OK/FAIL/RETRY)
- Decisión del router (stay/advance/jump/escalate)
- Trace completo con timestamps

**Esfuerzo**: 2h

---

## K10 — Tests de Integración

**Qué**: Tests que validan:
- Crear journey con 3 fases y 5 agentes → asignar a cliente → chatear → verificar avance
- Tag jump: LLM sugiere tag → Journey Engine valida → avanza
- Validación: JSON inválido → retry → escalation
- Multi-tenant: coach A no ve journeys del coach B

**Esfuerzo**: 3h

---

## Resumen

| K | Qué | Horas |
|---|-----|-------|
| K1 | Versionado | 2h |
| K2 | Tag transitions | 2h |
| K3 | Schema validation | 2h |
| K4 | RAG integration | 1h |
| K5 | Imprint → texto | 0.5h |
| K6 | Template placeholders | 1h |
| K7 | Bioneuro 15 pasos | 1h |
| K8 | Clonar journey | 1h |
| K9 | Monitor mejorado | 2h |
| K10 | Tests | 3h |
| **Total** | | **15.5h** |

**Arquitectura final** (todo data-driven):
```
Coach define via UI:
  Journey → Phases → Agents
  Cada agent: system_prompt + allowed_tags + output_schema
  Journey: tag_mappings + version

Runtime (genérico):
  compose_agent_prompt(template + placeholders + RAG + imprint)
  → LLM (DeepSeek)
  → validate_output(schema)
  → advance_client(tags, transitions)
  → audit log
```
