# Feature Specification: Voice Agent Nexus + Multi-Agent Swarm

**Branch**: `feat/voice-agent-nexus` | **Created**: 2026-05-22 | **Status**: Draft

## Research Summary (ctx7)

| Technology | What's New | Relevance |
|---|---|---|
| **LiveKit Agents** | STT-LLM-TTS pipeline maduro (Deepgram + GPT + Cartesia). `AgentSession` con VAD, noise cancellation, turn detection. 3.5k+ snippets. | Ready para reemplazar el actual stub de LiveKit |
| **OpenAI Realtime API** | GPT-5.x con audio-in/audio-out nativo vía WebRTC/WebSocket. Azure SDK disponible. | Alternativa directa a LiveKit pipeline |
| **LangGraph Swarm** | `create_swarm()` — multi-agent con routing nativo, listo para supervisar conversaciones. | Podemos reemplazar el orquestador manual con un swarm |
| **Cartesia Sonic-3** | TTS de baja latencia, voz natural. Integración directa con LiveKit Agents. | Mejor calidad de voz que la actual |

## User Stories

### US1 — Real-Time Voice Agent (P1)

Como cliente, quiero hablar con mi coach de voz en tiempo real (sin escribir) y que la conversación fluya naturalmente con detección de turns, noise cancellation y baja latencia.

**Independent Test**: Cliente llama → saluda → recibe respuesta de voz en <2s → conversación fluye por turns.

**Acceptance Scenarios**:
1. **Given** un cliente con micrófono, **When** inicia sesión de voz, **Then** el agente responde por voz en <2s
2. **Given** una conversación activa, **When** el cliente habla, **Then** el agente detecta el turno y responde sin overlap
3. **Given** ruido de fondo, **When** el cliente habla, **Then** el noise cancellation filtra el ruido

---

### US2 — Multi-Agent Swarm (P2)

Como coach, quiero que la conversación del cliente sea manejada por un swarm de agentes especializados (no un solo pipeline lineal) que se activen según el contexto de la conversación.

**Independent Test**: Cliente pregunta sobre finanzas → se activa agente financiero → responde → vuelve al agente principal.

**Acceptance Scenarios**:
1. **Given** una conversación sobre un tema específico, **When** el cliente menciona una keyword, **Then** el agente especializado toma el control
2. **Given** un agente especializado activo, **When** termina su tarea, **Then** el control vuelve al agente principal

---

### US3 — Coach Knowledge Hub (P2)

Como coach, quiero que mi knowledge base (materiales subidos + metodología) se indexe automáticamente con chunking inteligente y esté disponible para todos los agentes del swarm via RAG.

**Independent Test**: Coach sube PDF → se indexa → cliente pregunta sobre el tema → respuesta usa el contenido del PDF.

**Acceptance Scenarios**:
1. **Given** un PDF subido, **When** se completa el indexing, **Then** está disponible para consultas RAG en <30s
2. **Given** múltiples documentos, **When** se hace una query, **Then** el sistema hace cross-document retrieval

---

### US4 — Streaming TTS con Emoción (P3)

Como cliente, quiero que la voz del coach transmita empatía o urgencia según el contexto emocional detectado.

**Independent Test**: Cliente expresa frustración → la voz del coach suena más empática.

### US5 — Universal Data Collection (P0 — Core)

Como cliente, toda la información que proporciono durante un journey se guarda automáticamente en mi ficha de perfil, independientemente del formato JSON que use el agente.

**Independent Test**: Agente con formato `{"collected_data":{...}}` y otro con `{"structured":{"collected_data":{...}}}` — ambos guardan los datos en el shared profile.

**Acceptance Scenarios**:
1. **Given** un agente que responde con `{"collected_data": {"nombre": "Juan"}}`, **When** se procesa la respuesta, **Then** `nombre=Juan` se guarda en shared_profile
2. **Given** un agente que responde con `{"structured": {"collected_data": {"email": "j@c.com"}}}`, **When** se procesa, **Then** `email=j@c.com` se guarda
3. **Given** un agente que responde con `{"structured": {"edad": 30}}`, **When** se procesa, **Then** `edad=30` se guarda
4. **Given** datos ya existentes en shared_profile, **When** se guardan nuevos, **Then** se mergean sin perder los anteriores

### US6 — Coach Dashboard Profile View (P1)

Como coach, quiero ver una ficha del cliente con TODOS los datos recolectados durante los journeys, actualizada en tiempo real.

**Independent Test**: Cliente completa paso 1 de un journey → coach ve los datos en el dashboard.

**Acceptance Scenarios**:
1. **Given** un cliente con datos recolectados, **When** el coach abre su ficha, **Then** ve todos los campos recolectados
2. **Given** un cliente en medio de un journey, **When** el coach abre el dashboard, **Then** ve el progreso + datos acumulados

## Tech Stack Propuesto

| Componente | Tecnología | Razón |
|---|---|---|
| Voice pipeline | LiveKit Agents + Cartesia TTS + DeepGram STT | Maduro, open source, auto-hosting posible |
| Swarm orchestration | LangGraph `create_swarm()` | Ya usamos LangGraph, migración natural |
| Knowledge indexing | Qdrant + Gemini embeddings | Ya en producción |
| Noise cancellation | AiCoustics / Krisp | LiveKit Agents lo soporta nativamente |

## Success Criteria

- **SC-001**: Latencia voz <2s (STT → LLM → TTS)
- **SC-002**: Swarm maneja 5+ agentes sin degradación
- **SC-003**: RAG responde con documentos subidos en <1s
- **SC-004**: TTS emocional basado en sentiment analysis del clasificador
