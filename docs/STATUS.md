# KAIROS — Estado

> Última actualización: 2026-06-24

## Resumen
- Commits: 30+ recientes | Fases A-F + F0-F7 completadas | Tests: 37 | Migraciones en prod: 4
- Voice agent funcional (LiveKit + DeepGram + OpenAI + Cartesia)
- Journey coordinator system completo: transiciones con guards, fallback, derivación journey→journey

## ✅ Completado

### Fase A-F: Estabilización, Embeddings, Seguridad, Almacenamiento
- Fast path: 1 sola llamada LLM (de 4), latencia 1.8-2.6s
- Qdrant RAG: búsqueda semántica por coach_id + client_id
- MinIO: almacenamiento encriptado SSE-S3, aislado por coach/cliente
- Chunking: documentos de 800 chars con solapamiento 100
- Multi-tenant: coach_id en RawMemory, Qdrant, MinIO
- Auth PostgreSQL: coaches, sesiones, rate limiting por plan
- i18n: ES/EN, detección por cookie/query param

### Journey Engine
- `collects_fields`: campos por agente/fase declarados en BD
- `save_collected()`: transacción atómica client_journeys + shared_profiles
- `compose_agent_prompt()`: inyecta collected_data, RAG hits, impronta
- `advance_client()`: avance automático al completar campos
- Vital fields: normalización de aliases, sub-clave dedicada en shared_profiles
- **K7 (session resume)**: detección de gap >6h → inyecta saludo + recap en prompt

### F0-F7: Journey Coordinator System (refactor completo)
- **F0**: fast_path unificado con `validate_and_advance` (tags + saltos no-lineales). `journey_engine_v2` eliminado.
- **F1**: `turn_count` + `objective_state` en `client_journeys` con migración `l7m8n9o0p1q2`. Incrementa por turno, se resetea al transicionar.
- **F2**: `ObjectiveEvaluator` en `kairos/engine/objective_evaluator.py`. Modos: determinista (campos completos), LLM-judge opcional, híbrido. Persiste en `objective_state[agent_id]`.
- **F3**: `JourneyTransitionModel` con migración `m7n8o9p0q1r2`. `JourneyCoordinator` evalúa guards por prioridad: `turns`, `field`, `objective_met`. Compatible con `tag_mappings` existente.
- **F4**: `max_turns` + `fallback_agent_id` en `JourneyAgentModel`, migración `n7o8p9q0r1s2`. `_jump_to_agent()` para redirigir a agente concreto. Fallback automático si `turn_count >= max_turns` sin avance.
- **F5**: Derivación `journey→journey` vía transiciones con target `journey:<id>`. Usa `assign_client` (comparte `shared_profile`). Marca journey origen como `derived`.
- **F6**: Editor visual de transiciones en admin panel (sin JSON). Endpoints CRUD REST en `kairos/api/routes/journey_transitions.py`. Selector de guard: turns/field/objective_met + derivación a otro journey.
- **F7**: Tests de integración (10/10) ejecutados en prod contra la DB real. Cubren: lineal, tag jump, guard turns, guard field, fallback, derivación.

### Chat Interfaces
- Cliente: burbujas, markdown (marked.js), streaming, textarea auto-expandible
- Coach: split layout chat + sidebar (journey, progreso, ficha, tags)
- Voice overlay: 3 anillos, ecualizador, estados Escuchando→Procesando→Respondiendo
- LiveKit WebRTC: botón 📞 en client_chat, self-hosted en server

### Deploy
- Server: `95.217.217.222` — app, nginx, qdrant, postgres, minio, livekit
- Docker Compose producción con volume mounts para desarrollo activo
- Rsync sin rebuild (solo código Python)

### Migraciones aplicadas en prod
| ID | Descripción |
|---|---|
| `l7m8n9o0p1q2` | `client_journeys`: turn_count + objective_state |
| `m7n8o9p0q1r2` | `journey_transitions`: tabla con guards |
| `n7o8p9q0r1s2` | `journey_agents`: max_turns + fallback_agent_id |
| `k6l7m8n9o0p1` (previo) | coach_methodology_docs |

## ❌ Pendiente

| Feature | Prioridad | Esfuerzo estimado |
|---------|-----------|-------------------|
| UI: grafo visual de transiciones | Media | 3h |
| UI: loop test → mejora (sugerir fix y aplicar con 1 click) | Media | 3h |
| UI: monitor en vivo del coordinador (turn_count, objective_state) | Baja | 2h |
| K6 — Prompt template placeholders (algunos hechos) | Alta | 1h |
| Bioneuromoción agentes 2-15 (collects_fields) | Media | 2h |

## Servidores y acceso

| Servicio | URL |
|----------|-----|
| Web | https://api.ether.care |
| SSH | `ssh -i ~/.ssh/id_ed25519_opencode root@95.217.217.222` |

## Arranque

```bash
# Local dev
cd ~/Documents/KAIROS
source .venv/bin/activate
docker compose up -d qdrant postgres
cd kairos/db && alembic upgrade head && cd ../..
uvicorn kairos.api.server:app --host 127.0.0.1 --port 8000

# Deploy (solo código, sin rebuild)
rsync -avz -e "ssh -i ~/.ssh/id_ed25519_opencode" kairos/engine/journey_engine.py root@95.217.217.222:/opt/kairos/kairos/engine/journey_engine.py
ssh -i ~/.ssh/id_ed25519_opencode root@95.217.217.222 "cd /opt/kairos && docker compose -f docker-compose.prod.yml --env-file .env.production restart app"

# Deploy completo (con rebuild)
ssh -i ~/.ssh/id_ed25519_opencode root@95.217.217.222
cd /opt/kairos && git pull
docker compose -f docker-compose.prod.yml --env-file .env.production build app --no-cache
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --no-deps app

# Migración (aditiva, sin rebuild)
rsync -avz -e "ssh -i ~/.ssh/id_ed25519_opencode" kairos/db/migrations/versions/<file>.py root@95.217.217.222:/opt/kairos/kairos/db/migrations/versions/<file>.py
ssh -i ~/.ssh/id_ed25519_opencode root@95.217.217.222 "cd /opt/kairos && docker compose -f docker-compose.prod.yml --env-file .env.production exec -T app sh -c 'cd kairos/db && alembic upgrade head'"

# Tests de integración (contra DB de prod, datos con prefijo test_f7, auto-limpieza)
ssh -i ~/.ssh/id_ed25519_opencode root@95.217.217.222 "cd /opt/kairos && docker compose -f docker-compose.prod.yml --env-file .env.production exec -T app python kairos/tests/test_journey_coordinator_integration.py"
```

## Claves y credenciales
- DeepSeek ✅ | Gemini ✅ | Cartesia ✅ | DeepGram ✅ | LiveKit ✅ | OpenAI ✅
- MinIO ✅ | PostgreSQL ✅ | Qdrant ✅
- Twilio/WhatsApp ❌ | Stripe ❌

## Documentación de arquitectura
- `docs/JOURNEY_ENGINE_ARCHITECTURE.md` — estado actual, gaps, arquitectura objetivo, plan F0-F7
