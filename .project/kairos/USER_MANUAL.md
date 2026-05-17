# KAIROS — Manual de Usuario · Admin Panel

## Índice
1. [Conceptos clave](#1-conceptos-clave)
2. [Dashboard de Coaches](#2-dashboard-de-coaches)
3. [Gestor de Journeys](#3-gestor-de-journeys)
4. [Campos del Agente](#4-campos-del-agente)
5. [Tags y Transiciones](#5-tags-y-transiciones)
6. [Prompts del Sistema](#6-prompts-del-sistema)
7. [Canales (Telegram)](#7-canales-telegram)
8. [Monitor de Actividad](#8-monitor-de-actividad)
9. [Configuración del Coach](#9-configuración-del-coach)
10. [FAQ](#10-faq)

---

## 1. Conceptos Clave

| Término | Definición |
|---------|-----------|
| **Journey** | Un proceso completo de acompañamiento (ej: Coaching Personal, Bioneuromoción 12 Pasos) |
| **Fase** | Una etapa dentro del journey (ej: Diagnóstico, Claridad, Plan de Acción) |
| **Agente** | El "personaje" IA que interactúa con el cliente en una fase. Tiene su propio prompt, rol y objetivo |
| **System Prompt** | Las instrucciones detalladas que definen cómo se comporta el agente |
| **Allowed Tags** | Lista de etiquetas que el agente acepta como sugerencia de salto (ej: `["urgent","skip"])` |
| **Output Schema** | Define qué campos debe devolver el LLM en su respuesta JSON |
| **Impronta** | El "estilo" del coach: qué tan directivo, empático, formal es |

### Jerarquía
```
Journey (ej: "Coaching Personal")
  └── Fase 1: "Diagnóstico" (orden 0)
  │   └── Agente: "Explorador"
  │       ├── System Prompt: "Eres un coach en fase de diagnóstico..."
  │       ├── Allowed Tags: ["to_clarity"]
  │       └── Output Schema: {required_fields: ["message","structured"]}
  └── Fase 2: "Claridad" (orden 1)
      └── Agente: "Clarificador"
          └── ...
```

---

## 2. Dashboard de Coaches

**URL**: `/admin` (solo admin)

- **Tabla de coaches**: nombre, email, plan, idioma, rol
- **Botón "Editar"**: abre modal con todos los campos (nombre, email, plan, idioma)
- **Botón "Eliminar"**: solo para coaches no-admin
- **Botón "+ Nuevo coach"**: crea un coach con contraseña inicial

**Planes**:
- `free`: 60 req/min, solo web
- `pro`: 300 req/min, Telegram + web + MinIO
- `admin`: acceso total al panel

---

## 3. Gestor de Journeys

**URL**: `/admin/journeys`

### Crear un Journey
1. Clic en **"+ Nuevo journey"**
2. Rellenar:
   - **Nombre**: ej "Coaching Personal"
   - **Descripción**: qué hace este proceso
   - **Objetivo**: qué debe lograr el cliente
   - **Tipo**: coaching, comercial, financiero, bioneuro, custom
   - **Status**: draft (borrador) o active (activo)

### Editar un Journey
- Clic en **"Editar"** en la cabecera del journey
- Permite cambiar nombre, descripción, objetivo y status

### Añadir Fases
- Clic en **"+ Fase"** en la cabecera del journey
- Campos: Nombre, Objetivo, Orden (0 = primera)
- Las fases se ejecutan en orden (0, 1, 2...)

### Editar Fase
- Clic en **"Editar"** en la barra de la fase
- Permite cambiar nombre, objetivo y orden

### Añadir Agentes
- Clic en **"+ Agente"** en la barra de la fase
- Ver sección [Campos del Agente](#4-campos-del-agente)

---

## 4. Campos del Agente

Al crear o editar un agente, estos son los campos:

| Campo | Descripción | Ejemplo |
|-------|-------------|---------|
| **Nombre** | Identificador del agente | "Explorador" |
| **Rol** | Función que desempeña | "Diagnóstico inicial" |
| **Objetivo (goal)** | Qué debe conseguir | "Identificar situación, motivación y primer bloqueo" |
| **System Prompt** | ⭐ Instrucciones completas para el LLM. Soporta placeholders | Ver sección abajo |
| **Instrucciones adicionales** | Notas extra que se añaden al prompt | "Pregunta una cosa a la vez" |
| **Allowed Tags** | JSON array de tags que el agente acepta | `["urgent_followup","to_clarity"]` |
| **Output Schema** | JSON con campos requeridos en la respuesta | `{"required_fields":["message","structured","confidence"]}` |

### Placeholders disponibles en System Prompt

Estos se reemplazan automáticamente en runtime:

| Placeholder | Se reemplaza por |
|-------------|-----------------|
| `{{agent_name}}` | Nombre del agente |
| `{{step_title}}` | Nombre de la fase actual |
| `{{step_objective}}` | Objetivo de la fase |
| `{{client_snapshot}}` | Datos del perfil del cliente (JSON) |
| `{{shared_profile}}` | Ficha común completa (JSON) |
| `{{imprint_text}}` | Instrucciones de estilo según impronta del coach |
| `{{memory_hits}}` | Casos relevantes de la memoria (RAG) |

### Ejemplo de System Prompt con placeholders

```
Eres {{agent_name}}, agente en {{step_title}}.
Objetivo: {{step_objective}}

{{imprint_text}}

## Cliente
{{client_snapshot}}

{{memory_hits}}

Responde en JSON con los campos: message, structured, confidence, escalation_flag
```

---

## 5. Tags y Transiciones

Los tags permiten saltos NO lineales entre fases. Normalmente el journey avanza en orden (fase 1 → 2 → 3). Con tags, el LLM puede sugerir saltar directamente a otra fase.

### Cómo configurarlo

1. **En el agente**: define `allowed_tags` — qué tags acepta este agente
   ```json
   ["urgent_followup", "skip_to_closure"]
   ```

2. **En el journey** (próximamente en UI): define `tag_mappings` — a dónde lleva cada tag
   ```json
   {"urgent_followup": "phase_id_5", "skip_to_closure": "phase_id_15"}
   ```

3. **El LLM** sugiere un tag en `suggested_tags`:
   ```json
   {"suggested_tags": ["urgent_followup"], "confidence": 0.92}
   ```

4. **El Engine** valida: ¿está el tag en `allowed_tags`? ¿existe en `tag_mappings`? Si sí → salta a la fase indicada.

### Tags predefinidos disponibles

| Tag | Significado |
|-----|-------------|
| `urgent_followup` | El cliente necesita atención urgente → saltar a fase de seguimiento |
| `skip_to_closure` | El objetivo ya está cumplido → saltar a cierre |
| `to_clarity` | Avanzar a fase de claridad |
| `to_plan` | Avanzar a fase de plan de acción |
| `to_followup` | Avanzar a fase de seguimiento |
| `journey_complete` | Journey completado |
| `escalate` | Escalar a revisión humana |

Puedes definir tus propios tags en `allowed_tags` del agente.

---

## 6. Prompts del Sistema

**URL**: `/admin/prompts`

Estos NO son los prompts de los agentes del journey. Son prompts del **motor interno** del pipeline LangGraph:

| Agente | Función |
|--------|---------|
| `supervisor` | Decide qué perfil (coaching/comercial/financiero) usar |
| `analyst` | Analiza el contexto de la sesión y sugiere enfoque |
| `validator` | Evalúa la calidad de las respuestas del LLM |
| `classifier` | Clasifica emoción, riesgo, urgencia del mensaje |
| `synthesizer` | Extrae insights del cliente tras cada interacción |
| `coach_assistant` | Asistente RAG para preguntas del coach |

**Cuándo editarlos**: solo si necesitas afinar cómo el sistema clasifica, evalúa o analiza internamente. Para cambiar cómo el agente habla con el cliente, edita el System Prompt en el gestor de Journeys.

---

## 7. Canales (Telegram)

**URL**: `/admin/channels`

### Configurar Telegram para un coach
1. Clic en **"Configurar"** en la fila del coach
2. Rellenar:
   - **Bot Token**: token de @BotFather (ej: `123456:ABC-DEF...`)
   - **Nombre del bot**: username sin @ (ej: `luismartin_bot`)
   - **Chat ID**: para recibir alertas (opcional, de @userinfobot)
3. **Guardar**
4. Clic en **"Activar"** — esto enciende el bot y configura el webhook

### Cómo usa el cliente el bot
1. Busca `@nombre_del_bot` en Telegram
2. Envía `/start`
3. Se registra automáticamente como cliente del coach
4. Ya puede chatear — el bot usa el journey asignado

---

## 8. Monitor de Actividad

**URL**: `/admin/monitor`

4 tabs en tiempo real (actualización cada 15s):

| Tab | Qué muestra |
|-----|-------------|
| 📡 **Actividad** | Feed de eventos: mensajes entrantes, prompts usados, respuestas, asignaciones de journey |
| 🧭 **Journeys** | Tabla de clientes activos: journey, fase, progreso, última interacción |
| 🔍 **Trazas** | Últimas trazas de ejecución (datos técnicos) |
| 📋 **Eventos** | Eventos del journey: avances, saltos, asignaciones |

---

## 9. Configuración del Coach

**URL**: `/coach/settings`

### Journey por defecto
- Selector para elegir qué journey se asigna automáticamente a nuevos clientes
- Funciona para todos los canales (web, Telegram, futuro WhatsApp)

### Canales de notificación
- Email, SMS, Push, WhatsApp
- Frecuencia: Inmediato, Diario, Semanal
- Horas de silencio (no molestar)

### Impronta
**URL**: `/coach/imprint`

6 sliders que definen el estilo del coach:

| Slider | 0 | 10 |
|--------|---|----|
| Directividad | Sugiere sutilmente | Instruye con claridad |
| Emocionalidad | Neutro, analítico | Empático, expresivo |
| Analiticidad | Intuitivo | Basado en datos |
| Riesgo | Conservador | Desafiante |
| Formalidad | Coloquial | Formal, estructurado |
| Proactividad | Reactivo (responde) | Proactivo (propone) |

---

## 10. FAQ

**¿Puedo tener mis propios journeys además de los templates?**
Sí. Crea un journey con tipo "custom" y asígnale tus propias fases y agentes.

**¿Los cambios en un agente afectan a clientes que ya están en ese agente?**
Actualmente sí (próximamente con versionado, los clientes activos mantienen la versión con la que empezaron).

**¿Qué pasa si el LLM devuelve JSON inválido?**
El sistema reintenta 1 vez. Si sigue fallando, marca `escalation_flag=true` para revisión humana (próximamente).

**¿Puedo clonar un journey template para modificarlo?**
Próximamente (K8). Por ahora, crea uno nuevo manualmente.

**¿Cómo veo qué prompt se usó en una conversación?**
En el Monitor → tab Actividad, busca eventos tipo `prompt_used`. Muestra un preview del prompt enviado al LLM.

**¿Los clientes pueden tener más de un journey a la vez?**
No. Un cliente tiene un journey activo. Si se le asigna otro, reemplaza al anterior.
