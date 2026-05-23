# KAIROS — Deployment & Config Knowledge

## Server
- Host: `95.217.217.222`
- SSH: `ssh -i ~/.ssh/id_rsa root@95.217.217.222`
- App dir: `/opt/kairos`

## Deployment
- Usar **solo** `docker-compose.prod.yml` explícitamente:
  ```bash
  docker compose -f docker-compose.prod.yml --env-file .env.production up -d
  ```
- NO usar `docker compose` sin `-f` porque mergea `docker-compose.yml` (dev) y `docker-compose.prod.yml`, causando conflictos de healthchecks y configs de desarrollo.

## Volumen mounts (docker-compose.prod.yml)
`docker-compose.prod.yml` ahora tiene volume mounts para desarrollo activo:
- `./kairos:/app/kairos` — código fuente montado en vivo
- `./profiles:/app/profiles` — perfiles YAML
- `./obsidian_templates:/app/obsidian_templates`

**Esto significa que rsync de archivos funciona sin rebuild ni restart.** Solo hay que hacer rebuild si cambian dependencias (pyproject.toml), Dockerfile, o archivos estáticos que se copian en el build.

## Rsync changes to server
Los paths de rsync son **relativos al directorio raíz del proyecto**:

```bash
# Archivos individuales — usar path completo desde raíz
rsync -avz -e "ssh -i ~/.ssh/id_rsa" kairos/api/middleware.py root@95.217.217.222:/opt/kairos/kairos/api/middleware.py
rsync -avz -e "ssh -i ~/.ssh/id_rsa" kairos/web/templates/admin_journeys.html root@95.217.217.222:/opt/kairos/kairos/web/templates/admin_journeys.html

# Múltiples archivos del mismo directorio (cada uno a su destino individual)
rsync -avz -e "ssh -i ~/.ssh/id_rsa" \
  kairos/api/architect.py \
  root@95.217.217.222:/opt/kairos/kairos/api/architect.py
rsync -avz -e "ssh -i ~/.ssh/id_rsa" \
  kairos/engine/journey_architect/architect.py \
  root@95.217.217.222:/opt/kairos/kairos/engine/journey_architect/architect.py

# Directorio completo
rsync -avz -e "ssh -i ~/.ssh/id_rsa" kairos/web/templates/ root@95.217.217.222:/opt/kairos/kairos/web/templates/
```

## ⚠️ Errores comunes (NO repetir)
1. **Rsync con múltiples destinos NO funciona**: NO mezclar varios archivos locales con un solo destino remoto. Cada archivo necesita su propio rsync con path completo.
2. **Python NO recarga módulos automáticamente**: Los cambios en `.py` requieren `docker compose restart app`. Los templates `.html` sí se recargan solos (Jinja2).
3. **AuthMiddleware whitelist**: Al agregar nuevas rutas `/api/v1/*`, hay que agregarlas a la whitelist en `kairos/api/middleware.py` línea 27-31.
4. **Docker Compose mergea archivos**: `docker compose` sin `-f` mergea `docker-compose.yml` + `docker-compose.prod.yml`. Usar SIEMPRE `docker compose -f docker-compose.prod.yml`.
5. **`|first` en Jinja2 falla con secuencia vacía**: Usar `|map(attribute='name')|first|default('—')` en vez de `|first|attr('name')`.
6. **No existe `/opt/kairos/.env` en producción**: Eliminarlo si aparece, porque sobrescribe `.env.production` via docker compose.

## Full deploy (when rebuild needed)
```bash
git push
ssh -i ~/.ssh/id_rsa root@95.217.217.222
cd /opt/kairos && git pull   # only if remote is SSH-based
docker compose -f docker-compose.prod.yml --env-file .env.production build app --no-cache
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --no-deps app
```

## Archivos modificados para Journey Architect fix
- `kairos/api/architect.py` — `_get_coach` cambiado a cookie-based auth
- `kairos/engine/journey_architect/architect.py` — mejor error handling
- `kairos/web/templates/admin_journeys.html` — JS fixes, cleanup duplicado
- `kairos/api/middleware.py` — agregado `/api/v1/architect` a whitelist del AuthMiddleware
- `kairos/web/templates/admin.html` — agregado selector de journey por defecto en modal de edición de coach
- `kairos/api/routes/web.py` — admin route ahora carga journeys; update coach pasa `default_journey_id`

## Env files
- Producción: `/opt/kairos/.env.production` (usado con `--env-file`)
- Dev local: `/opt/kairos/.env`
- NO debe existir `/opt/kairos/.env` en producción (sobrescribe vars de `.env.production` via docker compose)

## Voice Agent System

### Arquitectura
```
Cliente (navegador) ──WebRTC──► LiveKit Server ──► voice_agent.py (STT→LLM→TTS)
                                      ▲
Cliente (chat UI) ──HTTP──► /api/v1/voice/token ──► LiveKit AccessToken
```

### Componentes

| Archivo | Rol |
|---|---|
| `kairos/engine/voice_agent.py` | LiveKit Agent Server. Pipeline: DeepGram STT → OpenAI/DeepSeek LLM → Cartesia Sonic-3 TTS + Silero VAD + AiCoustics noise cancellation + Multilingual turn detection |
| `kairos/api/routes/voice.py` | Endpoints: `GET /api/v1/voice/token` (genera token LiveKit), `POST /api/v1/voice/tts` (TTS vía Cartesia REST) |
| `kairos/engine/emotional_tts.py` | Mapea sentimiento del clasificador (positive/negative/urgent/neutral) → prompt + estilo de voz |
| `kairos/web/templates/client_chat.html` | Botón 📞 en input area → LiveKit client SDK → WebRTC room |

### Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/v1/voice/token` | Genera token JWT para room LiveKit del cliente. Requiere cookie `kairos_client_token` |
| POST | `/api/v1/voice/tts` | Text → audio WAV base64 vía Cartesia Sonic-3. Body: `{"text": "..."}` |
| WS | LiveKit URL | Conexión WebRTC directa con el voice agent |

### Env vars requeridas

```
LIVEKIT_URL=wss://tu-servidor-livekit.com
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
CARTESIA_API_KEY=...
DEEPGRAM_API_KEY=...
```

### Servicio Docker

```yaml
voice:
  build: .
  command: python -m kairos.engine.voice_agent start
  env_file: .env.production
```

### Dependencias (pyproject.toml)
```
voice = ["livekit-agents>=1.5", "livekit-plugins-cartesia", "livekit-plugins-silero",
         "livekit-plugins-deepgram", "livekit-plugins-openai", "livekit-plugins-ai-coustics"]
```

### LiveKit Config (livekit.yaml)
```yaml
port: 7880
rtc:
  use_external_ip: true          # requiere --node-ip=IP_PUBLICA
  tcp_port: 7881
  udp_port: 7882
keys:
  API_KEY: API_SECRET            # ≥32 chars cada uno
```

### Arquitectura de conexión
```
Browser ──wss://api.ether.care/livekit──► Cloudflare ──► nginx:80 ──► livekit:7880
Browser ──udp:7882──► LiveKit server (media directa, no pasa por nginx)
Voice Agent (Docker) ──ws://livekit:7880──► LiveKit server (señalización interna)
```

### Patrón correcto del voice agent (entrypoint)
```python
async def entrypoint(ctx: JobContext):
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    session = AgentSession(stt=deepgram.STT(...), llm=openai.LLM(...),
                           tts=cartesia.TTS(...), vad=silero.VAD.load())
    await session.start(
        room=ctx.room, agent=agent,
        room_input_options=RoomInputOptions(audio_enabled=True, close_on_disconnect=False),
        room_output_options=RoomOutputOptions(audio_enabled=True, transcription_enabled=True),
    )
    await session.generate_reply(instructions="Saluda...")
    # Sin loop — AgentSession auto-responde vía transcripción
```

### Puntos críticos (debugging histórico)
1. **`room_options` NO existe** como parámetro de `session.start()` — usar `room_input_options` y `room_output_options`
2. **`ctx.connect()` es obligatorio** — sin esto el agente no recibe tracks de audio
3. **`setMicrophoneEnabled(true)` en el JS** — el browser no publica mic automáticamente
4. **`transcription_enabled=True`** — necesario para que STT → LLM → TTS funcione
5. **Eventos de debug**: `session.on("user_input_transcribed")`, `room.on("track_subscribed")`, `room.on("participant_connected")`
6. **LiveKit UDP ports**: 7882/udp debe estar expuesto en el host y abierto en firewall
7. **`use_external_ip: true`** + `--node-ip=IP_PUBLICA` — necesario para ICE candidates correctos
8. **Hairpin NAT**: el agente dentro de Docker necesita `extra_hosts` o iptables para conectar a IP pública

## Servicios
| Servicio | Puerto interno | Healthcheck |
|----------|---------------|-------------|
| app | 8000 | curl http://localhost:8000/health |
| qdrant | 6333 | bash -c 'echo > /dev/tcp/localhost/6333' |
| postgres | 5432 | pg_isready |
| minio | 9000/9001 | curl http://localhost:9000/minio/health/live |
| nginx | 80/443 | — |

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
<!-- SPECKIT END -->
