# Findings — KAIROS

## Architectural Decisions

| Decision | Rationale | Date |
|----------|-----------|------|
| LangGraph over custom orchestration | Declarative graph, built-in state, streaming support | 2026-04-26 |
| Qdrant over Pinecone/Weaviate | Self-hosted, no lock-in, local dev with Docker | 2026-04-26 |
| YAML profiles | Non-developers can edit; decoupled from code | 2026-04-26 |
| 4-level memory (Raw→Case→Pattern→Execution) | Maps directly to KAIROS manifesto | 2026-04-26 |
| Flat AgentState | LangGraph reducers work better flat | 2026-04-26 |
| Scorer protocol | New algorithms = new class (open-closed) | 2026-04-26 |
| PostgreSQL default, SQLite fallback | Aligned with manifesto; asyncpg | 2026-04-26 |
| Jinja2 prompt templates | Battle-tested, sandboxable | 2026-04-26 |
| Decision formula: f(Perfil, Estado, Experiencia, Conocimiento) | Full 4-variable model from manifesto | 2026-04-26 |
| Agent pipeline: 11 nodos | perception → retrieve → score → aggregate → analyst → worker → validate → learn → client_synth → alert_check → obsidian | 2026-04-26 |
| Obsidian como capa de análisis | Local-first, Dataview queries sobre YAML frontmatter, sincronización bidireccional | 2026-04-26 |

## Validación con ctx7

| Tecnología | Versión | Hallazgo |
|-----------|---------|----------|
| **Obsidian Dataview** | — | Las queries DQL usan `FROM` con tags o carpetas. Los metadatos se definen en YAML frontmatter plano (no objetos Python). Los templates de KAIROS fueron corregidos para emitir frontmatter plano accesible por `TABLE nombre, emocion, score_global FROM #kairos/cliente SORT score_global ASC` |
| **Obsidian URI** | — | Esquema `obsidian://open?vault=` para abrir notas desde KAIROS. Útil para integración futura (ej: notificar al coach con deep link a la ficha del cliente). |
| **Seguridad local-first** | — | Obsidian almacena .md localmente. KAIROS escribe archivos planos. Sin dependencia de red. La bóveda puede estar en carpeta cifrada. |

## Correcciones aplicadas post-ctx7

1. **Frontmatter plano**: Las fichas de cliente ahora usan YAML plano (`emocion: ansioso`, `claridad: 0.3`) en vez de objetos Python anidados. Dataview puede consultarlos directamente.
2. **Dashboard Dataview**: El portafolio ahora usa `FROM #kairos/cliente` en vez de iteración Python. Las filas se generan dinámicamente en Obsidian.
3. **Alertas en dashboard**: Se referencian via `![[Alertas/_inbox.md]]` condicional.

## Client Module Additions

| Component | Archivo | Propósito |
|-----------|---------|-----------|
| `ClientProfile` | `core/client.py` | Entidad central del cliente |
| `ClientStore` | `memory/stores/client_store.py` | Perfiles + alertas en Qdrant |
| `ClientSynthesizer` | `engine/client_synthesizer.py` | Extrae insights vía LLM |
| `client_synthesizer_node` | `agents/nodes/client_synthesizer_node.py` | Nodo LangGraph que actualiza perfil |
| `analyst_node` | `agents/nodes/analyst_node.py` | Rol analista: revisa contexto+cliente |
| `alert_checker_node` | `agents/nodes/alert_checker.py` | Detecta crisis/estancamiento/resistencia |
| `ClientSimilarityScorer` | `memory/scoring.py` | Scoring consciente del cliente |
| clients API | `api/routes/clients.py` | CRUD de clientes + alertas |

## Obsidian / Coach-Side Additions

| Component | Archivo | Propósito |
|-----------|---------|-----------|
| `ObsidianWriter` | `engine/obsidian/writer.py` | Genera .md con frontmatter YAML + sintaxis Dataview |
| `obsidian_connector_node` | `agents/nodes/obsidian_connector.py` | Nodo LangGraph de sincronización |
| Templates | `obsidian_templates/` | 5 plantillas .md de referencia |
| Config parse | `engine/obsidian/writer.py::parse_config` | Lee Config.md del coach → overrides de impronta |

## Key Differences from v0 (PHRONOS)

- Renamed PHRONOS → KAIROS throughout
- Added StateClassifier (riesgo, emocion, urgencia, intencion, tono)
- Added KnowledgeRetriever (traditional RAG alongside experience)
- 4 memory levels instead of 1 (raw, case, pattern, execution)
- Agent flow: 11 nodos en pipeline secuencial
- Impronta ahora tiene `analiticidad` y `riesgo` como core fields + `ImprintMapper` conductual
- Módulo Cliente: perfiles, síntesis, alertas, scoring contextual
- Capa Obsidian: sincronización bidireccional, Dataview, Config.md
