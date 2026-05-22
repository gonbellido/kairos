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

## Volumen mounts críticos (docker-compose.yml, dev)
`docker-compose.yml` (dev) tiene volume mounts que NO están en `docker-compose.prod.yml`:
- `./kairos:/app/kairos` — código fuente montado en vivo
- `./profiles:/app/profiles` — perfiles YAML
- `./obsidian_templates:/app/obsidian_templates`

Esto significa que rsync de archivos funciona sin rebuild.

## Archivos modificados para Journey Architect fix
- `kairos/api/architect.py` — `_get_coach` cambiado a cookie-based auth
- `kairos/engine/journey_architect/architect.py` — mejor error handling
- `kairos/web/templates/admin_journeys.html` — JS fixes, cleanup duplicado
- `kairos/api/middleware.py` — agregado `/api/v1/architect` a whitelist del AuthMiddleware

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
