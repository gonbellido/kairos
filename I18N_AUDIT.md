# I18n Audit - KAIROS Platform

## 1. Inventory of Hardcoded Strings

### Frontend (Templates)
Most templates under `kairos/web/templates/` contain hardcoded Spanish strings.
- `base.html`: Sidebar labels ("Recursos", "Monitoreo", "Admin"), logout button ("Salir"), etc.
- `landing.html`: Introduction text.
- `login.html`: Form labels and button.
- `admin_*.html`: Dashboard titles, table headers, buttons, and helper texts.
- `coach/*.html`: Extensive Spanish content in dashboard, imprint, assistant, materials, and obsidian views.
- `client_*.html`: Client-facing dashboard, chat, and settings.

### Backend (API & Engine)
- `kairos/api/routes/web.py`: Default error messages and some titles in `_render` contexts.
- `kairos/api/routes/settings.py`: Error messages ("No autorizado", "Bio must be 200 characters or less").
- `kairos/engine/prompt_store.py`: All `DEFAULT_PROMPTS` are hardcoded in Spanish (except `validator` which is in English).
- `kairos/engine/notification_service.py`: Event types and messages are partially hardcoded or rely on dynamic content that is likely in Spanish.
- `kairos/engine/i18n.py`: Heuristic detection markers are hardcoded.

### Agents & Prompts
- System prompts for `supervisor`, `analyst`, `classifier`, `synthesizer`, and `coach_assistant` are predominantly Spanish.
- `validator` is in English.

## 2. Affected Files Grouped by Layer

### UI (Frontend)
- `kairos/web/templates/base.html`
- `kairos/web/templates/admin_journeys.html`
- `kairos/web/templates/admin_prompts.html`
- `kairos/web/templates/admin_monitor.html`
- `kairos/web/templates/admin_channels.html`
- `kairos/web/templates/coach/dashboard.html`
- `kairos/web/templates/coach/assistant.html`
- `kairos/web/templates/coach/imprint.html`
- `kairos/web/templates/coach/materials.html`
- `kairos/web/templates/coach/obsidian.html`
- `kairos/web/templates/coach/alerts.html`
- `kairos/web/templates/client_dashboard.html`
- `kairos/web/templates/client_chat.html`
- `kairos/web/templates/client_settings.html`
- `kairos/web/templates/client_login.html`
- `kairos/web/templates/landing.html`
- `kairos/web/templates/login.html`

### API & Middleware (Backend)
- `kairos/api/routes/web.py`
- `kairos/api/routes/settings.py`
- `kairos/api/routes/chat.py`
- `kairos/api/routes/clients.py`
- `kairos/engine/i18n.py`
- `kairos/api/middleware.py` (to be created or modified)

### Agents & Prompts
- `kairos/engine/prompt_store.py`
- `kairos/db/models.py` (`AgentPromptModel`)
- `kairos/engine/journey_engine.py`
- `kairos/agents/nodes/journey_agent.py`

### Database & Migrations
- `kairos/db/models.py`: Add `locale` to `CoachModel` (exists as `language`), `ClientSharedProfileModel`.
- `kairos/core/client.py`: Add `locale` to `ClientProfile`.
- New migration to add missing columns.

### Emails & Notifications
- `kairos/engine/notification_service.py`

## 3. Recommended Technologies
- **Backend/Templates**: Existing custom `I18nEngine` (will be expanded).
- **Frontend JS**: Simple `t()` helper if needed, but mostly handled by Jinja2 globals.
- **Extraction**: `i18next-parser`-like custom script to find missing keys.

## 4. Migration Plan

### Phase 1: Infrastructure & DB
1. Update `CoachModel`, `ClientProfile`, and `AgentPromptModel`.
2. Generate migrations.
3. Enhance `I18nEngine` to support prompt versioning by language.
4. Implement locale detection middleware.

### Phase 2: Backend & Agents
1. Move `DEFAULT_PROMPTS` to language files or split `AgentPromptModel` by language.
2. Update `PromptStore` to fetch prompts based on `locale`.
3. Localize API error messages and responses.

### Phase 3: Frontend Extraction
1. Extract all strings from templates to `es.json` and `en.json`.
2. Replace hardcoded strings with `{{ t('key') }}`.
3. Implement Language Selector in the header.

### Phase 4: Notifications & Quality
1. Localize webhooks/notifications.
2. Add tests for locale detection and agent response language.
3. Final review and terminology consistency.

## 5. Effort Estimation
- **Phase 1**: 2-3 hours
- **Phase 2**: 4-5 hours
- **Phase 3**: 6-8 hours
- **Phase 4**: 3-4 hours
**Total**: ~15-20 hours
