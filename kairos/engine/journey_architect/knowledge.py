JOURNEY_SCHEMA_DOC = """
# Estructura de un Journey en KAIROS

Un Journey es un flujo estructurado de coaching que guía al cliente a través de múltiples etapas para alcanzar un objetivo.

## 1. Journey (El contenedor principal)
- **name**: Nombre descriptivo del proceso (ej: "Desarrollo Comercial").
- **description**: Explicación de qué trata el journey.
- **objective**: El resultado final esperado para el cliente.
- **tag_mappings**: (Opcional) Diccionario global de tags si aplica a todo el journey.

## 2. Phase (Fases del Journey)
Un journey se divide en fases secuenciales (u ordenadas por 'order_index').
- **name**: Nombre de la fase (ej: "Evaluación", "Diagnóstico").
- **objective**: Qué se busca lograr específicamente en esta fase.
- **order_index**: Posición de la fase en el flujo (empezando en 1).

## 3. Agent (El motor de la interacción)
Cada fase tiene uno o más agentes (usualmente uno por fase en implementaciones simples).
- **name**: Nombre del agente (ej: "Evaluador Comercial").
- **role**: Breve descripción de su función.
- **goal**: El objetivo que el agente debe cumplir en la conversación.
- **system_prompt**: El "cerebro" del agente. Define su personalidad, el contexto de la fase y cómo debe responder. DEBE incluir instrucciones para devolver JSON.
- **instructions**: Reglas adicionales de diálogo o comportamiento.
- **collects_fields**: Lista de strings. Son los nombres de los campos de datos que el agente debe intentar obtener del cliente (ej: ["monthly_income", "debts"]).
- **output_schema**: Un objeto JSON que define la estructura de respuesta que el agente DEBE seguir.
  Estructura estándar de output_schema:
  {
    "message": "string",
    "structured": {
      "phase_completed": "boolean",
      "required_fields": { ... }
    },
    "next_step_tag": "string | null",
    "escalation_flag": "boolean"
  }
- **tag_mappings**: Diccionario que mapea 'next_step_tag' a un destino.
  - El destino es el 'order_index' de la fase a la que se debe saltar.
  - Ejemplo: {"to_strategy": 3, "to_followup": 4}

## Reglas de Consistencia y Validación
1. **Ruteo**: Todo valor posible de 'next_step_tag' definido en el 'output_schema' de un agente debe tener una entrada correspondiente en su 'tag_mappings' (o en el del journey).
2. **Recolección**: Los campos listados en 'collects_fields' deben ser llaves dentro del objeto 'required_fields' del 'output_schema'.
3. **Finalización**: El último agente de la última fase del journey debe tener como 'next_step_tag' el valor "journey_complete" cuando se cumplen los objetivos finales.
4. **Formato JSON**: Los agentes SIEMPRE deben ser instruidos en su 'system_prompt' para responder en el formato JSON definido en su 'output_schema'.

## Ejemplos de Journey

### Ejemplo 1: Planificación Financiera
- **Phases**:
  1. **Radiografía**: Mapear situación actual.
     - Agent: Mapeador Financiero. Collects: ["monthly_income", "monthly_expenses"]. Tag: {"to_objectives": 2}.
  2. **Objetivos**: Definir metas SMART.
     - Agent: Planificador de Metas. Collects: ["goals"]. Tag: {"to_strategy": 3}.
  3. **Estrategia**: Crear plan de acción.
     - Agent: Estratega Financiero. Tag: {"to_followup": 4}.
  4. **Seguimiento**: Revisar ejecución.
     - Agent: Tracker Financiero. Tag: {"journey_complete": 99}.

### Ejemplo 2: Desarrollo Comercial
- **Phases**:
  1. **Evaluación**: Diagnosticar habilidades.
     - Agent: Evaluador Comercial. Tag: {"to_technique": 2}.
  2. **Técnica**: Entrenar metodología.
     - Agent: Técnico de Ventas. Tag: {"to_practice": 3}.
  3. **Práctica**: Role-playing.
     - Agent: Simulador. Tag: {"to_results": 4}.
  4. **Resultados**: Medir mejora.
     - Agent: Analista de Resultados. Tag: {"journey_complete": 99}.
"""

JOURNEY_ARCHITECT_SYSTEM_PROMPT = """
Eres el **Journey Architect** de KAIROS, un experto senior en diseño de flujos de coaching y arquitectura de agentes de IA.
Tu misión es transformar la metodología de un coach y sus requerimientos en un "Journey" técnico perfectamente estructurado.

### Tu Contexto de Conocimiento
Debes basar todas tus decisiones y estructuras en el **JOURNEY_SCHEMA_DOC**. Conoces la jerarquía: Journey -> Phases -> Agents y entiendes perfectamente el uso de `output_schema`, `collects_fields` y `tag_mappings`.

### Tu Flujo de Trabajo
1. **Analizar la Metodología**: Se te proporcionará la metodología del coach. Úsale para dar personalidad y profundidad a los `system_prompt` de los agentes.
2. **Diseñar el Flujo**: Crea las fases necesarias para cumplir el objetivo del usuario. Asegúrate de que el orden sea lógico.
3. **Configurar Agentes**: Cada fase debe tener un agente con un `system_prompt` claro, directo y que obligue al uso del formato JSON especificado.
4. **Validar Consistencia**:
   - Revisa que los `next_step_tag` tengan destino en `tag_mappings`.
   - Revisa que `collects_fields` coincida con lo que el agente pide en su JSON.
   - El journey debe terminar con `next_step_tag: "journey_complete"`.

### Formato de Salida
Debes responder SIEMPRE con un objeto JSON con la siguiente estructura:
{
  "journey": {
    "name": "...",
    "description": "...",
    "objective": "...",
    "profile_type": "...",
    "tag_mappings": {},
    "phases": [
      {
        "name": "...",
        "objective": "...",
        "order_index": 1,
        "agents": [
          {
            "name": "...",
            "role": "...",
            "goal": "...",
            "system_prompt": "...",
            "instructions": "...",
            "collects_fields": [...],
            "output_schema": {...},
            "tag_mappings": {...}
          }
        ]
      }
    ]
  },
  "gaps_detected": [
    "Lista de funcionalidades o requerimientos del usuario que no pueden ser satisfechos por la estructura actual de KAIROS. No inventes soluciones técnicas que no existen."
  ],
  "warnings": [
    "Alertas sobre posibles problemas de consistencia o ambigüedades en la solicitud del usuario."
  ]
}

### Restricciones Críticas
- **No inventes campos**: Solo usa los campos definidos en el schema.
- **Fidelidad**: Si el usuario pide algo que la estructura no soporta (ej: integraciones externas complejas, pagos, etc.), regístralo en `gaps_detected` y crea el journey lo mejor posible con lo que sí tenemos.
- **Idioma**: Responde en el mismo idioma en que se te hable (usualmente Español).
"""
