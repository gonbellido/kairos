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

# Múltiples archivos del mismo directorio
rsync -avz -e "ssh -i ~/.ssh/id_rsa" \
  kairos/api/architect.py \
  kairos/engine/journey_architect/architect.py \
  root@95.217.217.222:/opt/kairos/kairos/

# Directorio completo
rsync -avz -e "ssh -i ~/.ssh/id_rsa" kairos/web/templates/ root@95.217.217.222:/opt/kairos/kairos/web/templates/
```

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

## Servicios
| Servicio | Puerto interno | Healthcheck |
|----------|---------------|-------------|
| app | 8000 | curl http://localhost:8000/health |
| qdrant | 6333 | bash -c 'echo > /dev/tcp/localhost/6333' |
| postgres | 5432 | pg_isready |
| minio | 9000/9001 | curl http://localhost:9000/minio/health/live |
| nginx | 80/443 | — |
