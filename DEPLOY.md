# KAIROS — Deployment Guide

## Subdominios necesarios

Apuntar estos 4 registros DNS tipo **A** a la IP del servidor:

| Subdominio | Propósito | Puerto |
|-----------|-----------|--------|
| `coach.tudominio.com` | Backoffice web del coach | 80/443 → Nginx → App:8000 |
| `api.tudominio.com` | API REST + SSE streaming | 80/443 → Nginx → App:8000 |
| `storage.tudominio.com` | MinIO Console (admin) | 80/443 → Nginx → MinIO:9001 |
| `s3.tudominio.com` | MinIO API (uploads) | 80/443 → Nginx → MinIO:9000 |

Ejemplo con dominio `kairos.app`:
```
coach.kairos.app   A  →  1.2.3.4
api.kairos.app     A  →  1.2.3.4
storage.kairos.app A  →  1.2.3.4
s3.kairos.app      A  →  1.2.3.4
```

Para Telegram, el webhook usa `https://api.tudominio.com/telegram/webhook`.

---

## Requisitos del servidor

- **Ubuntu 22.04 o 24.04** (LTS)
- **4 GB RAM mínimo** (8 GB recomendado)
- **20 GB disco** (50 GB+ recomendado para MinIO)
- **Docker** + **Docker Compose v2**
- **Puertos abiertos**: 80 (HTTP), 443 (HTTPS), opcionalmente 22 (SSH)

---

## Paso 1: Preparar el servidor

```bash
# Actualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Cerrar sesión y volver a entrar

# Instalar Docker Compose
sudo apt install -y docker-compose-plugin

# Verificar
docker --version
docker compose version
```

---

## Paso 2: Clonar el proyecto

```bash
git clone https://github.com/tu-org/kairos.git /opt/kairos
cd /opt/kairos
```

---

## Paso 3: Configurar entorno

```bash
# Copiar template de producción
cp .env.production .env.production.local

# Editar con tus secretos REALES
nano .env.production
```

**IMPORTANTE**: Cambiar TODOS los valores `REPLACE_WITH_*`:
- `POSTGRES_PASSWORD`: contraseña segura de 32+ chars
- `LLM_API_KEY`: tu API key de DeepSeek/OpenAI
- `GOOGLE_API_KEY`: tu API key de Google (Gemini embeddings)
- `MINIO_SECRET_KEY`: clave segura para MinIO
- `TELEGRAM_TOKEN`: token de BotFather (opcional)

---

## Paso 4: Desplegar

```bash
chmod +x deploy.sh
./deploy.sh
```

Esto:
1. Verifica Docker y dependencias
2. Valida `.env.production`
3. Construye la imagen de la app
4. Inicia todos los servicios (Nginx, App, Qdrant, PostgreSQL, MinIO)
5. Ejecuta migraciones de base de datos

---

## Paso 5: Verificar

```bash
# Estado de los servicios
docker compose -f docker-compose.prod.yml ps

# Logs de la app
docker compose -f docker-compose.prod.yml logs app -f

# Health check
curl http://localhost:8000/health
```

---

## Paso 6: Configurar SSL (HTTPS)

```bash
# Instalar certbot
sudo apt install -y certbot python3-certbot-nginx

# Obtener certificados (reemplaza con tu dominio)
sudo certbot --nginx -d coach.tudominio.com -d api.tudominio.com -d storage.tudominio.com -d s3.tudominio.com

# Verificar auto-renovación
sudo certbot renew --dry-run
```

---

## Comandos útiles

```bash
# Ver logs
docker compose -f docker-compose.prod.yml logs -f --tail=100 app

# Reiniciar app
docker compose -f docker-compose.prod.yml restart app

# Ejecutar migraciones manualmente
docker compose -f docker-compose.prod.yml exec app alembic -c /app/kairos/db/alembic.ini upgrade head

# Backup de PostgreSQL
docker compose -f docker-compose.prod.yml exec postgres pg_dump -U kairos kairos > db/backups/backup_$(date +%Y%m%d).sql

# Restaurar backup
docker compose -f docker-compose.prod.yml exec -T postgres psql -U kairos kairos < db/backups/backup_20260428.sql

# Acceder a MinIO Console
# Abrir https://storage.tudominio.com
# Login: MINIO_ACCESS_KEY / MINIO_SECRET_KEY

# Actualizar a nueva versión
git pull
docker compose -f docker-compose.prod.yml build app --no-cache
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml exec app alembic -c /app/kairos/db/alembic.ini upgrade head
```

---

## Monitoreo

```bash
# Métricas de la app (JSON)
curl https://api.tudominio.com/metrics

# Métricas en formato Prometheus
curl https://api.tudominio.com/metrics?format=prometheus

# Health check
curl https://api.tudominio.com/health
```

---

## Seguridad

- **Firewall**: solo puertos 80, 443, 22 abiertos. Qdrant (6333) y PostgreSQL (5432) no expuestos.
- **MinIO**: consola solo accesible vía Nginx (autenticada). API interna.
- **PostgreSQL**: solo accesible desde la red Docker interna.
- **Secrets**: nunca comitear `.env.production`. Usar variables de entorno o gestor de secretos.
- **Backups**: programar cron diario para `pg_dump`.

---

## Escalado

Para alta disponibilidad:
- **App**: escalar a múltiples réplicas con `docker compose up -d --scale app=3`
- **Qdrant**: usar cluster mode (3+ nodos)
- **PostgreSQL**: replicación streaming o managed (RDS, Cloud SQL)
- **MinIO**: modo distribuido (4+ nodos)
- **Load balancer**: Nginx o HAProxy delante de múltiples apps

---

## Troubleshooting

| Problema | Solución |
|----------|----------|
| `coaches table not found` | Ejecutar migraciones: `docker compose exec app alembic upgrade head` |
| Embeddings no funcionan | Verificar `GOOGLE_API_KEY` y `EMBEDDING_PROVIDER=google` |
| MinIO no accesible | Verificar `MINIO_ACCESS_KEY`/`MINIO_SECRET_KEY` coinciden |
| Telegram no responde | Verificar `TELEGRAM_TOKEN` y que el webhook esté accesible públicamente |
| 502 Bad Gateway | `docker compose logs app` — probablemente error de inicio |
