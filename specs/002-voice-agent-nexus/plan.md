# Implementation Plan: Voice Agent Nexus + Multi-Agent Swarm

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: LiveKit Agents, LangGraph >=0.2, Cartesia TTS, DeepGram STT
**Storage**: Qdrant (RAG), PostgreSQL (swarm state persistence)
**Testing**: pytest + LiveKit test harness

## Phase 0 — Universal Data Collection (P0 — Core)

Antes de cualquier feature nuevo, el sistema de recolección de datos debe funcionar para TODOS los journeys, independientemente del formato JSON.

**Fix**:
- `validate_and_advance()`: extraer `collected_data` de nivel raíz Y de `structured.collected_data` Y campos sueltos de `structured`
- `save_collected()`: mergear con shared_profile en vez de sobrescribir
- `journey_advance_node()`: misma lógica de extracción unificada
- Coach dashboard: mostrar `profile_data` del cliente con datos acumulados

**Archivos**: `kairos/engine/journey_engine.py`, `kairos/agents/nodes/journey_agent.py`, `kairos/web/templates/coach/client_detail.html`

## Status: All phases implemented ✅

### Phase 0 — Universal Data Collection ✅
### Phase 1 — LiveKit Agent Pipeline ✅
### Phase 2 — LangGraph Swarm ✅  
### Phase 3 — Coach Knowledge Hub ✅
### Phase 4 — Emotional TTS ✅

### Voice Journey System (additional)
- `channel` field en JourneyModel (text/voice/both) ✅
- `voice_default_journey_id` en CoachModel ✅
- Voice journey clonado y adaptado para voz ✅
- Admin UI: selector de journey de texto y voz ✅
- Filler LLM + KAIROS pipeline mix ✅

### Phase 0 — Universal Data Collection ✅
### Phase 1 — LiveKit Agent Pipeline ✅
### Phase 2 — LangGraph Swarm ✅  
### Phase 3 — Coach Knowledge Hub ✅
### Phase 4 — Emotional TTS ✅

## Original Plan (reference)

### Phase 1 — LiveKit Agent Pipeline (US1)
- Migrar del stub actual a `livekit-agents` con `AgentSession`
- Pipeline: DeepGram STT → OpenAI LLM → Cartesia TTS
- VAD con Silero + noise cancellation
- Voice worker como servicio separado en docker-compose
- **Archivos**: `kairos/engine/voice_agent.py` (reescribir), `docker-compose.prod.yml`

### Phase 2 — LangGraph Swarm (US2)
- Migrar el pipeline LangGraph actual a `create_swarm()`
- Agentes: supervisor, clasificador, coach principal, especialistas (financiero, salud, etc.)
- Swarm state persistence en PostgreSQL
- **Archivos**: `kairos/agents/orchestrator.py` (refactor), `kairos/agents/graphs/`

### Phase 3 — Coach Knowledge Hub (US3)
- Indexación automática de materiales subidos
- Chunking inteligente (preservar estructura de PDF/DOCX)
- Cross-document retrieval con reranking
- **Archivos**: `kairos/engine/chunker.py`, `kairos/engine/knowledge_retriever.py`

### Phase 4 — Emotional TTS (US4)
- Pipeline: classifier sentiment → Cartesia emotion params → TTS
- Emociones: empatía, urgencia, calma, entusiasmo
- **Archivos**: `kairos/engine/voice_agent.py`, `kairos/agents/nodes/perception.py`
