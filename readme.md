# KAIROS — Multi-Agent Framework for Coaching

Sistema multi-agente con memoria experiencial, perfiles conductuales (impronta),
análisis en Obsidian, bot de Telegram y backoffice web para coaches.

## Estado

**55 tests pasando · 65+ archivos Python · 16 nodos LangGraph · MVP funcional**

## Stack

| Componente | Tecnología |
|-----------|-----------|
| Orquestación | LangGraph 1.1+ |
| Memoria vectorial | Qdrant v1.13+ |
| LLM | OpenAI / DeepSeek / Anthropic |
| Embeddings | Gemini embedding-002 (multimodal) |
| API | FastAPI + SSE Streaming |
| Web UI | Jinja2 + Tailwind CSS (sin build) |
| Bot | python-telegram-bot |
| Análisis | Obsidian + Dataview |
| Audio | Whisper (openai-whisper) |
| DB | PostgreSQL (asyncpg) / SQLite |
| Infra | Docker Compose |

## Quick Start

```bash
# 1. Clonar e instalar
git clone <repo> && cd kairos
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 2. Configurar
cp .env.example .env
# Editar .env: LLM_API_KEY (DeepSeek/OpenAI)

# 3. Infraestructura
docker compose up -d qdrant postgres

# 4. Seed datos de ejemplo
source .venv/bin/activate
python scripts/seed_experience.py --sample

# 5. Arrancar servidor (en TERMINAL NUEVA)
uvicorn kairos.api.server:app --host 127.0.0.1 --port 8000
#   → http://127.0.0.1:8000/coach
```

## Arquitectura

```
Pipeline (16 nodos LangGraph):

supervisor → audio → perception → retrieve → score → aggregate → analyst
    │                                                                    │
  rutea perfil                                                    analiza contexto
    ↓                                                                    ↓
worker → validate → learn → client_synth → alert_check → impronta_learn → notify → obsidian → END

Decision = f(Perfil, Estado, Experiencia, Conocimiento, Cliente)
```

## Estructura

```
kairos/
├── core/              # Modelos: Profile, Impronta, Memory, Client, State
├── engine/            # Motores: prompt, scoring, clasificador, síntesis, impronta
├── agents/            # 16 nodos LangGraph + orquestador KairosRuntime
├── memory/            # 7 colecciones Qdrant + embeddings + scoring
├── api/               # FastAPI: REST + SSE + Web + Auth
├── web/               # Jinja2 templates + Tailwind CSS
├── db/                # SQLAlchemy + Alembic
├── plugins/           # Plugin system (post-MVP)
└── config/            # Pydantic Settings + Logging

profiles/              # Perfiles YAML (coaching, comercial, financiero)
scripts/               # Seed, pattern mining, bootstrap
tests/                 # 55 tests
obsidian_templates/    # Templates para bóveda Obsidian
```

## Documentación internas

- `.project/kairos/spec.md` — Especificación técnica completa
- `.project/kairos/plan.md` — Plan de desarrollo y roadmap
- `.project/kairos/findings.md` — Decisiones arquitectónicas
- `.project/kairos/status.md` — Status actual del proyecto
