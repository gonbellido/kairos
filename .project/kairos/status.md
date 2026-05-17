# KAIROS — Estado (2026-05-01 · deploy 08:20 UTC)

## Lo que funciona ✅

### Performance
| Métrica | Antes | Ahora |
|---------|-------|-------|
| "hola" | 13-40s | **1.8-2.6s** |
| LLM calls | 4 | **1** (fast path) |
| Gemini embeddings | 6-7 | **0** en fast path |
| Qdrant semantic | 5-6 queries | **0** en fast path |

### Journey — Intake y avance de fase
- `collects_fields` declarado en `JourneyAgentModel` → ya no llega vacío
- `compose_agent_prompt` lee de `client_journeys.collected_data` (fuente de verdad, no `shared_profiles`)
- Formato JSON unificado: solo `_build_format_instruction()` en `fast_path.py` lo inyecta (eliminado duplicado)
- Avance automático: `data_count >= min(len(collects_fields), 5)` → `advance_client()`
- Agente no reinicia preguntas: `collected_data` se inyecta en el prompt cada turno

### Sincronización de datos
- `save_collected()`: actualiza `client_journeys.collected_data` Y `shared_profiles.profile_data` en una transacción
- Campos vitales normalizados: aliases (`gender`→`sexo`, `phone`→`telefono`, etc.) resueltos automáticamente
- `vital_fields` guardados en sub-clave dedicada de `shared_profiles.profile_data`
- `advance_client()`: promueve `collected_data` → `shared_profiles` al avanzar fase (cross-journey persistence)
- `assign_client()`: pre-popula `collected_data` de journey nuevo con datos del `shared_profile` existente

### Ficha del cliente (coach dashboard)
- **Datos Vitales** (card teal): campos identificados por el sistema (`nombre`, `apellido`, `fecha_nacimiento`, `sexo`, `lateralidad`, `nacionalidad`, `provincia`, `email`, `telefono`, etc.) con etiquetas en español
- **Datos del Journey** (card gris): resto de campos recolectados por IA
- Ficha del journey → datos vitales separados visualmente del formulario manual

### RAG — Qdrant para agentes
- Antes de cada respuesta, `stream.py` busca en Qdrant:
  - **Coach KB** (`coach_id`, `client_id=""`, top 3, score > 0.5) → material/protocolos del coach
  - **Session history** (`client_id`, top 2, score > 0.5) → sesiones anteriores del cliente
- Resultados inyectados en `compose_agent_prompt()` como secciones separadas
- Graceful fallback: si Qdrant no responde o no hay hits relevantes, el prompt sigue funcionando normal

### Chat interfaces
- **Cliente**: rediseño completo — burbujas con avatar ◈ (agente) e inicial (cliente), markdown con marked.js, streaming token a token visible, textarea auto-expandible, Enter envía / Shift+Enter nueva línea
- **Voz (overlay)**: pantalla completa, 3 anillos de pulso animados, ecualizador 7 barras, estados Escuchando→Procesando→Respondiendo→Escuchando, auto-reinicio micrófono tras respuesta del agente
- **TTS**: Cartesia (si hay API key) con fallback a speechSynthesis nativa del browser
- **Coach**: nuevo split layout — chat izquierda + sidebar derecha con journey, fase, barra de progreso, ficha completa, tags, estado emocional, tareas, botón "Avanzar fase"
- **Ruta nueva**: `GET /coach/chat/{client_id}` carga journey + collected_data + perfil coach

### Deploy (2026-05-01 08:20 UTC)
- Server: `95.217.217.222` — todos los servicios up (app, nginx, qdrant, postgres, minio, livekit)
- Código sincronizado vía rsync (257 archivos), app reiniciada con "KAIROS system initialized"
- Migraciones DB aplicadas: `tag_mappings`, `collects_fields`, `collected_data`, `current_phase_order` — todas existentes
- `collects_fields` actualizados para 9 agentes de Coaching Personal y Desarrollo Comercial (antes vacíos → ahora con campos por fase)

## Archivos clave

| Archivo | Rol |
|---------|-----|
| `kairos/engine/vital_fields.py` | Registry de campos vitales + normalización de aliases |
| `kairos/engine/journey_engine.py` | `save_collected`, `compose_agent_prompt`, `advance_client` |
| `kairos/paths/fast_path.py` | Entrada fast path, extrae data, llama `save_collected` |
| `kairos/api/routes/stream.py` | SSE + RAG Qdrant + routing fast/deep |
| `kairos/api/routes/web.py` | Rutas coach: dashboard, client_detail, chat |
| `kairos/web/templates/coach/client_detail.html` | Ficha con Datos Vitales + Journey |
| `kairos/web/templates/coach/chat.html` | Coach chat con sidebar |
| `kairos/web/templates/client_chat.html` | Cliente chat con voz |
| `kairos/db/models.py` | `collects_fields`, `tag_mappings` en `JourneyAgentModel` |

## DB migrations (aplicadas en server)

Todas las columnas existen en producción:
```sql
-- ✅ Aplicadas:
ALTER TABLE journey_agents ADD COLUMN IF NOT EXISTS tag_mappings JSONB DEFAULT '{}';
ALTER TABLE journey_agents ADD COLUMN IF NOT EXISTS collects_fields JSONB DEFAULT '[]';
ALTER TABLE client_journeys ADD COLUMN IF NOT EXISTS collected_data JSONB DEFAULT '{}';
ALTER TABLE client_journeys ADD COLUMN IF NOT EXISTS current_phase_order INTEGER DEFAULT 1;
ALTER TABLE journey_agents ADD COLUMN IF NOT EXISTS phase_order INTEGER DEFAULT 0;
```

## collects_fields por journey (DB actualizada)

| Journey | Agente | collects_fields |
|---------|--------|----------------|
| Coaching Personal | Explorador | client_name, context, goal, blocker |
| Coaching Personal | Clarificador | smart_goal, success_criteria, timeline |
| Coaching Personal | Planificador | tasks |
| Coaching Personal | Accountability | completed_tasks, blockers_resolved |
| Coaching Personal | Integrador | learnings, next_steps |
| Desarrollo Comercial | Evaluador Comercial | strengths, gaps, current_pipeline |
| Desarrollo Comercial | Técnico de Ventas | techniques_practiced, objection_responses |
| Desarrollo Comercial | Simulador | scenarios_completed, feedback_summary |
| Desarrollo Comercial | Analista de Resultados | improvement_pct, next_targets |
| Bioneuromoción 15 Pasos | Recepcionista | nombre, apellido, fecha_nacimiento, sexo, lateralidad, nacionalidad, provincia |

## Pendiente / Nice-to-have

- [ ] LiveKit agent service real (requiere `LIVEKIT_URL` + credenciales + agente Python activo) — server ya tiene LiveKit corriendo en puertos 7880-7881
- [ ] Deep path: `classifier` puede mandar a DEEP pero el path no ejecuta LangGraph todavía
- [ ] `coach/chat.html`: el botón "Avanzar fase" llama a `POST /api/v1/clients/{id}/journey/advance` — revisar que el sidebar se recargue con datos nuevos
- [ ] Limpiar nodos viejos: `supervisor.py`, `response_validator.py` (no se usan en fast path)
- [ ] Bioneuromoción 15 Pasos: agentes 2-15 siguen con `collects_fields = []` (solo Recepcionista tiene campos) — evaluar si necesitan campos también
- [ ] Fase K (Journey System Reutilizable): K1-K10 planeado en `PHASE_K_PLAN.md` (15.5h estimadas)
