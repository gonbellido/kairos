# KAIROS — Plan de Desarrollo

**Estado**: MVP funcional · Fases A+B+C+D+E completadas · **Tests**: 55 · **Última actualización**: 2026-04-28

---

## Fase A — Estabilización ✅ COMPLETADA (2026-04-28)

(ver detalles abajo)

---

## Fase B — Optimización de Ingesta y Memoria ✅ COMPLETADA (2026-04-28)

---

## Fase C — Confiabilidad y Observabilidad ✅ COMPLETADA (2026-04-28)

### C1. Structured logging con trace_id por request ✅
- `kairos/config/trace.py`: `TraceContext` con `contextvars`
- `TraceMiddleware` genera `trace_id` por request, header `X-Trace-Id`
- `StructuredFormatter` y `JSONFormatter` incluyen trace context
- `orchestrator.py` propaga session_id, profile_id, coach_id

### C2. Métricas de pipeline ✅
- `kairos/engine/metrics.py`: latencia por nodo (avg/p50/p95/p99), hit rate N1/N2/N3, composite_score
- Nodos instrumentados con `_timed()`, endpoint `GET /metrics`, log cada 50 requests

### C3. Auth en PostgreSQL ✅
- Tablas `coaches` y `coach_sessions`, `CoachDBA` async con SQLAlchemy
- Migración Alembic, `web.py` y `coach_assist.py` actualizados

### C4. Rate limiting por coach_id ✅
- Key por `coach_id` vía cookie, fallback a IP
- Límites por plan: `RATE_LIMIT_FREE`/`RATE_LIMIT_PRO`

---

## Fase D — Funcionalidades Avanzadas ✅ COMPLETADA (2026-04-28)

### D1. Conditional branching en LangGraph ✅
- `_build_graph()` usa `add_conditional_edges` en 3 puntos:
  - **Audio**: solo si `_audio_bytes` o `_audio_path` en contexto
  - **Analyst**: solo si `client_id` presente en contexto (~30% de requests)
  - **Obsidian**: solo si `OBSIDIAN_VAULT` configurado
- Reduce latencia significativamente en requests sin audio ni cliente

### D2. Multi-modelo: evaluador con modelo distinto ✅
- `llm_factory.py`: `create_eval_llm()` usa `EVALUATOR_MODEL` de settings
- Soporte para providers: OpenAI, DeepSeek, Anthropic (via openai-compat)
- `analyst_node` y `response_validator` usan `eval_llm` (modelo evaluador)
- Worker usa `self.llm` (modelo generación, más barato)
- Si `EVALUATOR_MODEL == LLM_MODEL`: log informativo sugiriendo separarlos

### D3. Multi-Agente: cross-profile memory sharing ✅
- `retrieve_node`: búsqueda en perfiles "hermanos" configurada
  - Coaching ↔ Comercial (casos comerciales útiles para coaching y viceversa)
  - Financiero → Coaching + Comercial
- `CROSS_PROFILES` dict configurable, `CROSS_TOP_K=3` casos por perfil hermano
- `cross_profile: true/false` en contexto para desactivar

### D4. Plugin System ✅
- `BasePlugin`: 6 hook points (`before_prompt`, `after_llm`, `before_store`, `after_validate`, `before_response`, `on_session_end`)
- `PluginLoader`: carga dinámica por dotted path + configuración por perfil
- `run_hook()`: ejecuta hooks en cadena para un perfil
- `worker_node` y `response_validator` integran `plugin_loader`
- Plugin ejemplo: `SafetyFilter` (content safety en after_llm)
- `on_session_end` fire-and-forget en `run()`

### D5. Optimización de memoria y caching ✅
- `kairos/engine/cache.py`: `LRUCache` in-memory con TTL
  - `_embedding_cache`: 2000 entradas, TTL 1h
  - `_llm_cache`: 500 entradas, TTL 5min
- `kairos/memory/bayesian.py`: `BayesianScorer` con Thompson sampling
  - Beta(alpha + successes, beta + failures) ponderado
- Prometheus format: `GET /metrics?format=prometheus`
  - Métricas: `kairos_requests_total`, `kairos_node_latency_ms`, `kairos_cache_size`

---

## Fase E — Multilenguaje ✅ COMPLETADA (2026-04-28)

### E1. i18n Engine ✅
- `kairos/engine/i18n.py`: `I18nEngine` con carga lazy de traducciones JSON
- Soporte: Español (`es`) e Inglés (`en`)
- Detección automática por query param `?lang=`, cookie `kairos_lang`, o heurística de texto
- Archivos: `kairos/i18n/es.json` (90+ keys UI + prompts), `kairos/i18n/en.json` (90+ keys)
- Secciones: `ui` (interfaz web) y `prompts` (system prompts)

### E2. Middleware de idioma ✅
- `LanguageMiddleware` en `server.py`: detecta y configura idioma por request
- Cookie `kairos_lang` con 30 días de persistencia
- `_render()` helper en `web.py` inyecta `lang` en todos los templates

### E3. Templates con i18n ✅
- Función `t(key)` disponible en Jinja2 globals para traducciones inline
- `base.html` usa `lang` dinámico en `<html lang="{{ lang }}">`
- Todas las respuestas de template pasan por `_render()` que inyecta idioma

---

## Fase F — Auditoría de Ingesta, Embeddings, Seguridad y Almacenamiento ✅ COMPLETADA (2026-04-28/29)

### F1-F8: Diagnóstico y corrección de embeddings ✅
(Ver detalle en sección anterior)

### F9: Chunking de documentos ✅
- `kairos/engine/chunker.py`: divide documentos en chunks de 800 chars con solapamiento de 100
- Cada chunk se embebe independientemente → búsqueda semántica encuentra cualquier parte del documento
- Lista de materiales agrupa chunks por `document_id`
- Delete elimina todos los chunks del documento

### F10: MinIO — Almacenamiento seguro de documentos ✅
- `kairos/storage/minio_client.py`: `SecureStorage` con:
  - **Aislamiento por cliente**: ruta `{coach_id}/{client_id}/{unique}_{filename}`
  - **Encriptación SSE-S3**: server-side encryption con AES256
  - **SHA-256**: hash de integridad en metadata
  - **Pre-signed URLs**: acceso temporal para descargas
- `docker-compose.yml`: servicio MinIO (puertos 9000 API, 9001 consola)
- `upload.py`: audios y documentos de cliente → MinIO + embedding
- `materials.py`: materiales del coach → MinIO + chunking + embedding
- `settings.py`: `MINIO_HOST`, `MINIO_PORT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_ENCRYPTION`

### F11: Obsidian — Diagnóstico ✅
- Vault existe en `/Users/gbellido/Documents/KAIROS-Vault/KAIROS/`
- Estructura de carpetas creada (Clientes, Alertas, Dashboard, Metodología)
- La sincronización ocurre cuando el pipeline procesa sesiones con clientes
- Página Obsidian ahora muestra documentos desde Qdrant + MinIO, no solo archivos .md del vault

### F12: Chunking de documentos ✅
- `kairos/engine/chunker.py`: chunks de 800 chars con solapamiento de 100
- Cada chunk con su propio vector embedding
- Materiales agrupados por `document_id` en lista
- Búsqueda semántica encuentra cualquier parte del documento

### F13: MinIO Secure Storage ✅
- `kairos/storage/minio_client.py`: SSE-S3, SHA-256, paths aislados por coach/cliente
- `docker-compose.yml`: servicio MinIO (puertos 9000/9001)
- Integrado en `upload.py` y `materials.py`

---

## Fase G — Gestión de Coaches, Canales y Multi-Idioma ← ACTIVA

### G1: Edición de coaches ✅ (2026-04-29)
- `CoachDBA.update_coach()`: edita nombre, email, plan, idioma, contraseña
- `PUT /admin/coach/{coach_id}`: endpoint REST
- `admin.html`: modal unificado crear/editar con selector de plan (free/pro/admin) e idioma (ES/EN)
- `CoachModel.language`: nueva columna (migración `d4e5f6a7b8c9`)
- Sidebar: "Métricas" removido, Admin solo visible para admins

### G2: Gestor de planes 📋
- **Free**: 60 req/min, 5 clientes, sin WhatsApp, sin Telegram, solo web
- **Pro**: 300 req/min, clientes ilimitados, WhatsApp + Telegram + Web, MinIO, RAG avanzado
- **Admin**: ilimitado, acceso total al panel

### G3: Idioma por coach 📋
- Preferencia guardada en `coaches.language`
- Templates y UI en ES/EN según preferencia

### G4: Canales de integración 📋

| Canal | Estado | Stack |
|-------|--------|-------|
| Web Chat | 📋 | Widget JS embebible, SSE streaming |
| Telegram | 🟡 | Ya existe bot, falta UI gestión |
| WhatsApp | 📋 | Twilio/WhatsApp Business API |
| API REST | ✅ | `/api/v1/chat`, streaming SSE |

### G5: UI de gestión de canales 📋
- Panel `/admin/channels`: estado, config, estadísticas, logs

---

## Errores de Planteamiento Críticos (diagnóstico 2026-04-27)

### Arquitectura de almacenamiento (post-Fase F)

```
┌──────────────────────────────────────────────────────┐
│                   Cliente sube archivo               │
└────────────────────┬─────────────────────────────────┘
                     │
         ┌───────────▼───────────┐
         │   MinIO (encriptado)  │  ← Almacenamiento seguro
         │  kairos-documents/    │    {coach_id}/{client_id}/
         │  SSE-S3 + SHA-256     │
         └───────────┬───────────┘
                     │
         ┌───────────▼───────────┐
         │   Text Extractor      │  ← Extracción de texto
         │   (PDF, DOCX, RTF...) │
         └───────────┬───────────┘
                     │
         ┌───────────▼───────────┐
         │   Chunker             │  ← División en chunks
         │   (800 chars, 100 ov) │
         └───────────┬───────────┘
                     │
         ┌───────────▼───────────┐
         │   Google Gemini       │  ← Embedding multimodal
         │   (3072d vectors)     │
         └───────────┬───────────┘
                     │
         ┌───────────▼───────────┐
         │   Qdrant              │  ← Búsqueda semántica
         │   raw_memories        │    filtrada por coach_id
         └───────────────────────┘    + client_id
```

### Diagnóstico inicial — 8 bugs encontrados

| # | Bug | Severidad | Impacto |
|---|-----|-----------|---------|
| F1 | `coach_assist.py` usaba `query_points` con vector `[0.0]*3072` | CRÍTICO | El listado de materiales devolvía basura. Mismo anti-patrón ya corregido en A4, C3 y materials.py |
| F2 | Material se embebía como bytes (multimodal) pero la búsqueda era por texto | CRÍTICO | **Espacios vectoriales incompatibles.** El embedding multimodal de un PDF nunca es cercano al embedding de texto de una pregunta. El agente NUNCA encontraba los materiales. |
| F3 | Sin `coach_id` en materiales — todos los coaches compartían el mismo pool | CRÍTICO | **Data leak multi-tenant.** Coach A veía materiales del Coach B. |
| F4 | Código muerto: el `materials` list construido con zero-vector nunca se usaba | ALTO | ~15 líneas de código inútil |
| F5 | `raw_store` no soportaba filtro por `coach_id` | ALTO | Sin aislamiento por coach en ninguna búsqueda |
| F6 | `RawMemory` no tenía campo `coach_id` | ALTO | Modelo de datos incompleto para multi-tenant |
| F7 | El prompt del coach_assistant no diferenciaba materiales globales vs. del coach | MEDIO | Confusión en el contexto |
| F8 | Sin tests de integración para el flujo upload → search → assistant | MEDIO | Imposible validar regresiones |

### Correcciones aplicadas

### F1+F2: Arreglo de búsqueda semántica ✅
- `coach_assist.py`: eliminado el `query_points` con vector cero. Reemplazado por `raw_store.search_relevant()` que hace **embedding de texto real**.
- `materials.py`: el upload ahora embebe el **texto extraído** del documento (no los bytes). Esto garantiza que el espacio vectorial sea compatible con las queries de texto del coach assistant.
- **Resultado**: si subes la "guía maestra" y preguntas por ella, el agente SÍ la encuentra porque el embedding de la pregunta y el embedding del texto del documento están en el mismo espacio vectorial.

### F3: Aislamiento multi-tenant por coach_id ✅
- `RawMemory` ahora tiene campo `coach_id`
- `materials.py` upload: extrae `coach_id` del token de sesión y lo almacena
- `materials.py` list: filtra por `coach_id` del coach autenticado
- `coach_assist.py` search: filtra por `coach_id` del coach autenticado
- **Resultado**: cada coach solo ve y busca sus propios materiales. Aislamiento total.

### F4: Código muerto eliminado ✅
- Eliminado el segundo paso en `coach_assist.py` que construía `materials` con zero-vector y nunca lo usaba
- El flujo ahora es: 1 solo paso de búsqueda semántica real → contexto → asistente

### F5: raw_store con soporte coach_id ✅
- `search()`, `search_relevant()`, `list_by_filter()` aceptan `coach_id`
- El filtro se aplica solo si el valor es no-vacío (compatible hacia atrás)

---

## Errores de Planteamiento Críticos (diagnóstico 2026-04-27)

1. Pipeline de embeddings falla en silencio → corregido en A1
2. Extractores de documentos sin señal → corregido en A3
3. Memoria sin purga ni deduplicación → corregido en B3, B5
4. StateClassifier solo regex → corregido en B1
5. Flat TypedDict sin reducers → Documentado, no crítico con grafo secuencial
6. ClientProfile con vector cero → corregido en A4
7. Auth local en JSON plano → corregido en C3

---

## Cómo arrancar el servidor

```bash
cd ~/Documents/KAIROS
source .venv/bin/activate
docker compose up -d qdrant postgres
cd kairos/db && alembic upgrade head && cd ../..
uvicorn kairos.api.server:app --host 127.0.0.1 --port 8000
```

Endpoints clave:
- `http://127.0.0.1:8000/coach` — Dashboard (español por defecto)
- `http://127.0.0.1:8000/coach?lang=en` — Dashboard en inglés
- `GET /metrics` — Métricas JSON
- `GET /metrics?format=prometheus` — Métricas Prometheus text format
- `GET /health` — Health check

Para seed de datos:
```bash
python scripts/seed_experience.py --sample
```

---

## Problemas conocidos post-Fase E

1. **Migración requiere PostgreSQL**: `docker compose up -d postgres` antes de `alembic upgrade head`
2. **CoachDB JSON legacy**: El archivo `kairos_coaches.json` ya no se usa
3. **Telegram/Obsidian**: Configurar `TELEGRAM_TOKEN` y `OBSIDIAN_VAULT` en `.env`
4. **Multi-modelo**: Configurar `EVALUATOR_MODEL` distinto a `LLM_MODEL` para aprovechar D2
5. **Idioma**: Templates aún tienen texto hardcoded en español — la infraestructura i18n está lista para migración progresiva
