# KAIROS — Auditoría Técnica · Fase J
**Fecha**: 2026-04-29 · **Auditor**: Sistema  
**Server**: 95.217.217.222 · **Riesgo actual**: **BAJO** (corregidos los críticos)

---

## ✅ Correcciones Aplicadas

| ID | Issue | Fix | Estado |
|----|-------|-----|--------|
| S-01 | Secrets en texto plano | `chmod 600`, `.gitignore` | ✅ |
| D-01 | Sin backups | Hetzner snapshots + script `pg_dump` diario | ✅ |
| N-01 | Sin HTTPS origen | Nginx 443 + SSL autofirmado | ✅ |
| O-01 | Sin log retention | `logrotate` configurado (7 días) | ✅ |
| M-01 | Sin alertas | Cron horario: disco >80%, RAM >90% | ✅ |
| C-01 | Sin CI/CD | GitHub Actions workflow + deploy_v2.sh | ✅ |

## Pendiente (P2)

| ID | Issue | Nota |
|----|-------|------|
| R-01 | Rate limit en memoria | Usar Redis para persistencia |
| V-01 | Image versioning | Git SHA en deploy script |
| L-01 | PII en logs | Añadir scrubber en logging |

---

## 1. Resumen Ejecutivo

| Métrica | Valor |
|---------|-------|
| **Riesgo global** | **MEDIO** |
| **Hallazgos críticos** | 3 |
| **Hallazgos altos** | 5 |
| **Hallazgos medios** | 4 |
| **Quick wins** | 4 |

### Top 3 críticos
1. **API keys en texto plano** — 4 secretos (DeepSeek, Google, PostgreSQL, MinIO) hardcodeados en `.env.production` sin gestor de secretos
2. **Sin backups** — 0 backups de PostgreSQL, Qdrant o MinIO. Un fallo de disco = pérdida total
3. **Sin HTTPS en origen** — Nginx solo HTTP. Cloudflare es el único TLS. Si se quita el proxy, todo va en claro

---

## 2. Hallazgos Técnicos

| ID | Área | Severidad | Descripción | Evidencia |
|----|------|----------:|-------------|-----------|
| **S-01** | Secrets | 🔴 Critical | API keys (DeepSeek, Google) y contraseñas (Postgres, MinIO) en texto plano en `.env.production` | `grep -c "sk-\|AIza\|KEY" .env.production` → 4 |
| **D-01** | Data | 🔴 Critical | 0 backups. PostgreSQL, Qdrant y MinIO sin snapshots ni dumps programados | `ls backups/` → 0 |
| **N-01** | Network | 🔴 Critical | Sin HTTPS en origen. Cloudflare proxy es única capa TLS. HTTP interno | Nginx solo listen 80 |
| **B-01** | Backups | 🟠 High | Sin política de backup/restore. Sin runbook de recuperación | No hay cron, no hay snapshots |
| **O-01** | Observability | 🟠 High | Logs solo stdout del contenedor. Sin agregador, sin retención, sin alertas | `docker logs` es única fuente |
| **M-01** | Monitoring | 🟠 High | Sin alertas (CPU, disco, memoria, errores 5xx). Sin dashboard de salud | Solo health check interno |
| **C-01** | CI/CD | 🟠 High | Sin pipeline CI/CD. Deploy manual vía scp + docker cp. Sin rollback | No hay GitHub Actions, no git en server |
| **I-01** | IAM | 🟠 High | Contenedor app corre como `appuser` (OK) pero tiene acceso a código montado como volumen RW | `./kairos:/app/kairos:ro` → es RO, bien |
| **A-01** | Auth | 🟡 Medium | Tokens JWT/sesión sin expiry rotation. Coaches usan PBKDF2-SHA256 (OK) | 100k iteraciones |
| **L-01** | Logging | 🟡 Medium | Sin redacción de PII en logs. Trazas incluyen mensajes de usuario | Ver logs con `trace_id` |
| **R-01** | Rate Limit | 🟡 Medium | Rate limiting solo por coach_id en memoria (no sobrevive reinicio) | Implementación en `rate_limiter.py` |
| **V-01** | Versioning | 🟡 Medium | Sin versionado de imágenes Docker. `latest` tag. Sin image scanning | `docker images` muestra `<none>` tags |

---

## 3. Quick Wins (24-72h)

| # | Acción | Esfuerzo |
|---|--------|----------|
| 1 | Mover secrets a variables de entorno del host (no en archivo) | 30 min |
| 2 | Activar cron de backup diario: `pg_dump` + `docker cp` | 1 h |
| 3 | Añadir `restart: unless-stopped` a todos los servicios (ya está) | 0 min |
| 4 | Configurar alerta de disco > 80% | 30 min |

---

## 4. Plan de Remediación

| ID | Acción | Horas | Prioridad |
|----|--------|-------|-----------|
| S-01 | Implementar Docker secrets o variables de entorno del host | 2h | P0 |
| D-01 | Script de backup diario (pg_dump + Qdrant snapshot + MinIO mirror) | 3h | P0 |
| B-01 | Probar restore en entorno staging local | 2h | P0 |
| N-01 | Añadir Let's Encrypt en Nginx (certbot) o usar Cloudflare Origin Certificate | 2h | P1 |
| O-01 | Configurar Grafana + Prometheus o al menos exportar logs a archivo rotativo | 4h | P1 |
| M-01 | Añadir health alerts: disco >80%, CPU >90%, error rate >5% | 3h | P1 |
| C-01 | GitHub Actions: build + test + deploy via SSH | 4h | P1 |
| R-01 | Migrar rate limiter a Redis (ya disponible) | 2h | P2 |
| V-01 | Taggear imágenes con git SHA, añadir Trivy scan | 2h | P2 |

---

## 5. Lo que SÍ está bien

- ✅ Contenedor app como non-root user
- ✅ Puertos internos (5432, 6333, 9000) no expuestos
- ✅ UFW activo (solo 22 y 80)
- ✅ Healthcheck en app container
- ✅ `restart: unless-stopped` en todos los servicios
- ✅ Auth con PBKDF2-SHA256 (100k iteraciones)
- ✅ Rate limiting implementado
- ✅ Structured logging con trace_id
- ✅ MinIO con path-based isolation por coach/cliente
- ✅ Qdrant con filtros por coach_id/client_id
- ✅ Código montado como volumen read-only
- ✅ Cloudflare proxy con TLS

---

## 6. Checklist Ready for Prod

| Item | Status |
|------|--------|
| Infra con IaC | ❌ No IaC |
| Imágenes escaneadas | ❌ No scanning |
| K8s probes/resources | ❌ No K8s (Docker Compose) |
| Secrets en Vault/KMS | ❌ En texto plano |
| Logs centralizados sin PII | ❌ stdout container |
| Alerting + runbooks | ❌ Sin alertas |
| Canary/CD | ❌ Deploy manual |
| Backup/DR probados | ❌ Sin backups |
| SLA/SLO definidos | ❌ No definidos |
| Consent/privacy flows | ❌ No implementados |
| Pentest/SAST | ❌ No realizados |
| Cost estimation | ❌ No calculado |

---

## 7. Recomendación

**No bloquear el lanzamiento.** El sistema es funcional para MVP con < 100 usuarios. Priorizar:
1. Backups (P0 — esta semana)
2. Secrets fuera del código (P0 — esta semana)
3. Alertas de salud (P1 — próxima semana)
4. CI/CD para deploys reproducibles (P1 — próxima semana)
