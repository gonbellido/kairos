# KAIROS — Especificación Técnica

**Status**: draft
**Versión**: 0.1.0

## 1. Visión del Sistema

Framework multi-agente que captura, replica y potencia el **criterio humano** mediante una **Memoria de Experiencia Ponderada** de 4 niveles. No solo busca información (RAG clásico), sino que decide **cómo** intervenir basándose en éxtos y fracasos previos.

**Decisión = f(Perfil, Estado, Experiencia, Conocimiento)**

## 2. Stack Tecnológico (Verificado con ctx7)

| Componente | Versión | Uso |
|-----------|---------|-----|
| Python | 3.13 | Lenguaje base |
| LangGraph | 1.1.9 | Orquestación de agentes (StateGraph) |
| langchain-core | 1.3.2 | Mensajes (SystemMessage, HumanMessage) |
| langchain-openai | 1.2.1 | LLM (ChatOpenAI) |
| qdrant-client | 1.17.1 | Memoria vectorial (query_points API) |
| FastAPI | 0.136.1 | API REST |
| Pydantic | 2.13.3 | Schemas + Settings |
| SQLAlchemy 2.0 | async | ORM (PostgreSQL) |

## 3. Arquitectura

### Pipeline de Agentes (LangGraph StateGraph)

```
START → perception → memory → worker → evaluator → END
```

Cada nodo muta el `AgentState` (TypedDict plano). No hay comunicación directa entre agentes — todo fluye a través del estado.

### Nodos

| Nodo | Función | Estado que consume | Estado que produce |
|------|---------|-------------------|-------------------|
| **perception** | Clasifica entrada (riesgo, emoción, urgencia, intención, tono) | `message` | `state_classification` |
| **memory** | Recupera de los 4 niveles + RAG conocimiento + scoring | `message`, `profile_id` | `raw_memories`, `retrieved_cases`, `ranked_cases`, `patterns`, `knowledge_docs` |
| **worker** | Resuelve perfil+impronta, construye prompt, llama LLM | `profile_id`, `state_classification`, `ranked_cases`, etc. | `prompt`, `llm_response`, `impronta` |
| **evaluator** | Evalúa respuesta, almacena caso+execution | `llm_response`, `impronta`, `message` | `evaluation`, `final_response`, `execution` |

## 4. Los 4 Niveles de Memoria

| Nivel | Colección Qdrant | Contenido | Uso |
|-------|-----------------|-----------|-----|
| N1: Raw | `raw_memories` | Transcripciones, logs, texto sin procesar | Contexto histórico crudo |
| N2: Cases | `cases` | Contexto + Intervención + Impronta + Outcome | Experiencia estructurada (Core) |
| N3: Patterns | `patterns` | Insights con señal estadística | Detección de patrones |
| N4: Execution | `executions` | Output en tiempo real | Auditoría y trazabilidad |
| Knowledge | `knowledge` | Documentación técnica | RAG clásico |

## 5. API (FastAPI)

```
POST /api/v1/chat
{
  "session_id": "default",
  "profile_id": "coaching",
  "message": "Estoy estancado en mi carrera",
  "user_id": "user-1",
  "context": {}
}
→
{
  "session_id": "default",
  "response": "¿Qué significa 'estancado' para ti?",
  "confidence": 0.85,
  "profile_id": "coaching",
  "classification": {"riesgo": 0.0, "emocion": "negative", "urgencia": 0.0, ...}
}
```

## 6. Modelo de Impronta

Variables [0.0, 1.0] que definen el comportamiento del perfil:

| Variable | Descripción |
|----------|-------------|
| `directividad` | 0=sugerir, 1=instruir |
| `emocionalidad` | 0=lógico/frío, 1=empático |
| `analiticidad` | 0=intuitivo, 1=data-driven |
| `riesgo` | 0=conservador, 1=agresivo |
| `formalidad` | 0=coloquial, 1=formal |
| `proactividad` | 0=reactivo, 1=propositivo |
| `estructura` | 0=libre, 1=metodológico |
| `personalizacion` | 0=genérico, 1=altamente personalizado |
| `extra` | Dimensiones adicionales por perfil |

Las improntas se cargan desde YAML y se integran al prompt vía Jinja2.

## 7. Algoritmo de Scoring

Pluggable via protocol `Scorer`. Cada scorer implementa:
```python
class Scorer(ABC):
    name: str
    weight: float
    async def score(case: ScoredCase, context: dict) -> float
```

Scorers por defecto:
- **SemanticScorer** (weight: 0.35) — similitud coseno de Qdrant
- **RecencyScorer** (weight: 0.25) — decaimiento exponencial por días
- **OutcomeScorer** (weight: 0.25) — basado en outcome + feedback
- **FrequencyScorer** (weight: 0.15) — penaliza sobre-uso
- **ContextualScorer** (weight: 0.10) — matching de estado emocional/intención
- **ClientSimilarityScorer** (weight: 0.15) — matching con perfil del cliente

Compuesto: `Σ(score_i * weight_i)`.

## 8. Módulo Cliente

### 8.1 ClientProfile — Entidad central

Cada cliente del coach tiene un perfil completo que se actualiza automáticamente:

```python
class ClientProfile(BaseModel):
    id: str
    coach_id: str
    nombre: str
    metadata: dict          # edad, contexto, notas
    objetivos: list[ClientObjective]
    estado_actual: ClientState   # emocional, claridad, energia, resistencia
    historial: dict              # sesiones, mensajes
    patrones_detectados: list[ClientPattern]
    insights: list[ClientInsight]
    progreso: ClientProgress     # score_global + señales (claridad, accion, apertura, consistencia)
    alertas_activas: list[Alert]
```

### 8.2 Mecanismo de actualización

El `client_synthesizer` (nodo LangGraph) ejecuta después de cada interacción:

1. Recibe el mensaje original + la respuesta del coach
2. LLM extrae: estado emocional, claridad, energía, resistencia, insights, patrones
3. `apply_synthesis()` actualiza el `ClientProfile` en Qdrant
4. Las señales se recalcularon → `score_global` se actualiza

### 8.3 Alertas automáticas

| Alerta | Condición | Nivel | Acción |
|--------|-----------|-------|--------|
| `alta_resistencia` | resistencia ≥ 0.7 | high | notify_coach |
| `estancamiento` | claridad ≤ 0.2 | medium | adjust_response |
| `crisis_emocional` | emocional = "crisis" | urgent | notify_coach |
| `baja_energia` | energia ≤ 0.2 | low | adjust_response |

### 8.4 API de clientes

```
GET    /api/v1/clients?coach_id=...      → lista de clientes
GET    /api/v1/clients/{id}              → perfil completo
PUT    /api/v1/clients/{id}              → actualizar perfil/objetivos
GET    /api/v1/clients/{id}/alerts       → alertas del cliente
GET    /api/v1/clients/alerts/active     → alertas globales activas
```

## 9. Multi-Agente por Roles (Simplificado)

El pipeline actual asigna roles claros a cada nodo:

| Nodo | Rol | Responsabilidad |
|------|-----|-----------------|
| `perception` | **analizador de input** | Clasifica estado (riesgo, emoción, urgencia) |
| `retrieve` + `score` + `aggregate` | **analista de memoria** | Recupera, pondera y agrega experiencias |
| `analyst` | **analista de contexto** | Revisa perfil del cliente, patrones, genera recomendación |
| `worker` | **coach** | Genera la intervención principal con todo el contexto |
| `validate` | **evaluador** | Valida calidad, impronta y anti-patrones |
| `client_synth` + `alert_check` | **observador/aprendiz** | Actualiza perfil y detecta alertas (no interviene) |

No hay debate complejo entre agentes. La colaboración es pipeline: cada nodo recibe el estado acumulado del anterior.

## 10. Grafo Completo (KAIROS + Cliente)

```
START → perception → retrieve → score → aggregate → analyst → worker
                                                              ↓
                                                         validate
                                                              ↓
                                                          learn
                                                              ↓
                                                     client_synth
                                                              ↓
                                                     alert_check
                                                              ↓
                                                            END
```

## 11. UX (Producto Mínimo)

### Coach:
1. Login → Dashboard con lista de clientes
2. Selecciona cliente → ficha con:
   - Resumen emocional (estado actual + señales)
   - Evolución de score_global (histórico simple)
   - Alertas activas (rojo/amarillo/verde)
   - Objetivos (editable)
   - Patrones detectados
3. Botón "Nueva sesión" → inicia chat contextualizado

### Cliente:
- Interfaz de chat simple
- Sin login
- Las respuestas son coherentes porque el sistema usa:
  - Su perfil como contexto
  - Experiencias previas del coach
  - Patrones detectados

## 13. Estados del Desarrollo

| Fase | Estado | Descripción |
|------|--------|-------------|
| **Core MVP** | ✅ **100%** | 11 nodos pipeline, 6 scorers, 4 niveles memoria, 3 perfiles, 48 tests |
| **Módulo Cliente** | ✅ **100%** | ClientProfile, ClientStore, ClientSynthesizer, analyst node, alert_checker, API CRUD, scoring contextual |
| **Capa Obsidian** | ✅ **100%** | ObsidianWriter, obsidian_connector node, templates Dataview, Config.md parser, frontmatter plano |
| **Feedback Loop** | ⏳ 0% | Endpoint feedback, re-scoring automático |
| **Multi-Agente** | ⏳ 0% | Supervisor routing, cross-profile, debate |
| **Plugins** | ⏳ 0% | Hook system, ejemplos por perfil |
| **Optimización** | ⏳ 0% | Bayesian scoring, auto-insights, caching |
| **Producción** | ⏳ 0% | Auth, rate limit, streaming, Whisper |

### Resumen: 48 tests · 59 archivos Python · 11 nodos LangGraph · 7 colecciones Qdrant · 5 templates Obsidian

## 10. Infraestructura

```yaml
docker-compose:
  services:
    - qdrant (puerto 6333)
    - postgres:16 (puerto 5432)
    - app (FastAPI, puerto 8000)
```

Variables de entorno vía `.env` con prefijo `KAIROS_`.

## 14. Capa de Análisis y Visualización (Coach-Side via Obsidian)

### 14.1 Concepto: The Intelligent Vault

Obsidian actúa como **exo-cerebro analítico** del coach. La sincronización es bidireccional:

```
KAIROS ──(push)──→ Obsidian: fichas de cliente, dashboards, alertas
Obsidian ──(pull)──→ KAIROS: instrucciones calientes, notas de sesión
```

### 14.2 Estructura de Carpetas en la Bóveda

```
📁 Vault/
└── 📁 KAIROS/
    ├── 📄 Portafolio.md              ← Dashboard con Dataview
    ├── 📄 Config.md                  ← Instrucciones calientes (coach → KAIROS)
    ├── 📁 Clientes/
    │   ├── 📁 Ana_García/
    │   │   ├── 📄 Ana_García.md      ← Ficha dinámica (Frontmatter + Dataview)
    │   │   ├── 📁 Bitácora/          ← Resúmenes automáticos de interacciones
    │   │   └── 📁 Alertas/           ← Notas de alerta
    │   └── 📁 Juan_Pérez/...
    ├── 📁 Alertas/
    │   └── 📄 _inbox.md              ← Inbox de alertas activas
    └── 📁 Metodología/
        └── 📄 patrones.md            ← Patrones transversales detectados
```

### 14.3 Templates Markdown

**Ficha de Cliente** (ejemplo generado automáticamente):

```markdown
---
id: c1
nombre: "Ana García"
tags: [#kairos/cliente #ansioso]
---

# 👤 Ana García

> [!warning] Estado Actual
> **Emocional:** ansioso · **Claridad:** 30% · **Energía:** 40% · **Resistencia:** 70%

```dataview
TABLE round(score_global * 100) as "Score Global" ...
```

## 📈 Progreso — Score Global: 35%
## 🧠 Patrones: lenguaje negativo (×3), evasión (×1)
## 💡 Insights: "Tiene miedo al cambio"
## 📁 Sesiones: 4 · Mensajes: 23
```

**Dashboard de Portafolio** (Dataview + alertas):

```markdown
| Cliente |   | Ánimo    | Progreso | Alertas |
|---------|---|----------|----------|---------|
| Ana     | 🟡 | ansioso  | 35%      | 2       |
| Luis    | 🟢 | motivado | 78%      | 0       |
```

**Config.md** (coach → KAIROS):

```yaml
# Impronta Override por cliente
ana_garcia: { directividad: 0.7, emocionalidad: 0.4 }

# Instrucciones generales
"Hoy quiero un enfoque más confrontacional con Juan"
```

### 14.4 Obsidian Connector (Nodo LangGraph)

Nuevo nodo en el pipeline: `obsidian_connector`

```
... → alert_check → obsidian_connector → END
```

Responsabilidades:
1. Recibir `AgentState` completo post-ejecución
2. Generar/actualizar ficha de cliente en Markdown
3. Escribir alertas como notas independientes
4. Actualizar dashboard si corresponde
5. Parsear `Config.md` para extraer overrides de impronta

El nodo es **best-effort**: si la bóveda no está configurada (`OBSIDIAN_VAULT=""`), se skipea silenciosamente.

### 14.5 Obsidian Canvas como Mapa de Proceso

El coach puede crear un Canvas `.canvas` que referencie notas de KAIROS:

```
[Bloqueo: resistencia alta] ──→ [Caso similar #42] ──→ [Intervención sugerida]
         │                                                   │
         └── [Conversación N1: "no puedo"] ────────────────┘
```

Cada nodo del Canvas es un wiki-link a una nota generada por KAIROS o una nota escrita por el coach.

### 14.6 Privacidad y Seguridad (Local-First)

| Principio | Implementación |
|-----------|---------------|
| Datos locales | La bóveda Obsidian es local. Nunca se sube a la nube |
| Sin dependencia de red | El writer escribe archivos locales, sin HTTP |
| Encriptación | La bóveda puede estar en una carpeta cifrada (Cryptomator, FileVault) |
| Coherencia | KAIROS es la fuente de verdad. Obsidian es una vista. Los datos maestros están en Qdrant |
| Config sensible | `OBSIDIAN_VAULT` se define en `.env`, no en código |

### 14.7 Flujo de Sincronización Completo

```
Interacción
    ↓
KAIROS pipeline (10 nodos)
    ↓
obsidian_connector:
    1. ¿Vault configurado? No → skip
    2. ensure_structure() — crea carpetas si no existen
    3. write_client_profile() — actualiza ficha .md
    4. Si alerta → write_alert() — escribe nota en Alertas/
    5. Si refresh_dashboard → write_dashboard()
    6. write_config_template() — asegura que Config.md existe
    ↓
Coach abre Obsidian:
    - Ve dashboard actualizado con Dataview
    - Abre ficha del cliente con estado en tiempo real
    - Edita Config.md para cambiar impronta
    ↓
Siguiente interacción:
    obsidian_connector.parse_config() → extrae overrides
    → los inyecta en el state antes de perception
```

### 14.8 Implementación Técnica

| Componente | Archivo |
|-----------|---------|
| `ObsidianWriter` (engine) | `kairos/engine/obsidian/writer.py` |
| `obsidian_connector_node` | `kairos/agents/nodes/obsidian_connector.py` |
| Templates .md | `obsidian_templates/` (5 templates) |
| Config setting | `OBSIDIAN_VAULT` en env vars |
| Tests | `tests/test_obsidian.py` (8 tests) |

## 15. Infraestructura

## 16. Principios de Diseño

1. **Desacoplamiento**: Core independiente de perfiles. Perfil nuevo = YAML nuevo.
2. **Extensibilidad**: Scorers, stores y plugins via protocolos/ABC.
3. **Independencia de Modelo**: Scoring corre fuera del LLM.
4. **Auditabilidad**: Cada respuesta tiene `decisions[]` con trazabilidad completa.
5. **Aprendizaje At-Retrieval**: El aprendizaje ocurre al seleccionar qué experiencias recuperar.
