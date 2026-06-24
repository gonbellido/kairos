# KAIROS — Estado

> Última actualización: 2026-05-28

## Resumen
- Commits: 20+ recientes | Fases A-F completadas | Fase K pendiente | Tests: 55
- Voice agent funcional (LiveKit + DeepGram + OpenAI + Cartesia)

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

### Chat Interfaces
- Cliente: burbujas, markdown (marked.js), streaming, textarea auto-expandible
- Coach: split layout chat + sidebar (journey, progreso, ficha, tags)
- Voice overlay: 3 anillos, ecualizador, estados Escuchando→Procesando→Respondiendo
- LiveKit WebRTC: botón 📞 en client_chat, self-hosted en server

### Deploy
- Server: `95.217.217.222` — app, nginx, qdrant, postgres, minio, livekit
- Docker Compose producción con volume mounts para desarrollo activo
- Rsync sin rebuild (solo código Python)

## ❌ Pendiente

| Feature | Prioridad | Esfuerzo estimado |
|---------|-----------|-------------------|
| K1 — Versionado de journeys | Alta | 2h |
| K2 — Tag-based transitions | Alta | 2h |
| K3 — OUTPUT_SCHEMA validation | Alta | 2h |
| K4 — RAG/CaseStore integrado al journey | Media | 1h |
| K5 — Imprint → texto automático | Media | 0.5h |
| K6 — Prompt template placeholders | Alta | 1h |
| K7 — Bioneuromoción 15 pasos (template) | Media | 1h |
| K8 — Clonar journey | Media | 1h |
| K9 — Monitor de ejecución mejorado | Baja | 2h |
| K10 — Tests de integración journey | Alta | 3h |
| Bioneuromoción agentes 2-15 (collects_fields) | Media | 2h |

## Servidores y acceso

| Servicio | URL |
|----------|-----|
| Web | https://api.ether.care |
| SSH | `ssh -i ~/.ssh/id_rsa root@95.217.217.222` |

## Arranque

```bash
# Local dev
cd ~/Documents/KAIROS
source .venv/bin/activate
docker compose up -d qdrant postgres
cd kairos/db && alembic upgrade head && cd ../..
uvicorn kairos.api.server:app --host 127.0.0.1 --port 8000

# Deploy (solo código, sin rebuild)
rsync -avz -e "ssh -i ~/.ssh/id_rsa" kairos/engine/journey_engine.py root@95.217.217.222:/opt/kairos/kairos/engine/journey_engine.py
ssh -i ~/.ssh/id_rsa root@95.217.217.222 "cd /opt/kairos && docker compose -f docker-compose.prod.yml --env-file .env.production restart app"

# Deploy completo (con rebuild)
ssh -i ~/.ssh/id_rsa root@95.217.217.222
cd /opt/kairos && git pull
docker compose -f docker-compose.prod.yml --env-file .env.production build app --no-cache
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --no-deps app
```

## Claves y credenciales
- DeepSeek ✅ | Gemini ✅ | Cartesia ✅ | DeepGram ✅ | LiveKit ✅ | OpenAI ✅
- MinIO ✅ | PostgreSQL ✅ | Qdrant ✅
- Twilio/WhatsApp ❌ | Stripe ❌
