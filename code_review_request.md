# Code Review Request: Journey Architect Agent

I have implemented the Journey Architect Agent, which allows coaches to create and manage structured journeys using natural language, informed by their own methodologies.

## Key Changes:
- **Database**: Added `coach_methodology_docs` table and SQLAlchemy model. Created Alembic migration `k6l7m8n9o0p1`.
- **Knowledge Base**: Defined `JOURNEY_SCHEMA_DOC` and `JOURNEY_ARCHITECT_SYSTEM_PROMPT` in `kairos/engine/journey_architect/knowledge.py`. This serves as the agent's brain.
- **Store**: Implemented `CoachMethodologyStore` for per-coach methodology document management.
- **Agent**: Created `JourneyArchitect` in `kairos/engine/journey_architect/architect.py`. It handles LLM interaction, spec validation, and sequence creation (Journey -> Phase -> Agent).
- **API**: Added endpoints in `kairos/api/routes/architect.py` for building, creating, explaining, and methodology management. Registered in `server.py`.
- **UI**: Added a sliding "Journey Architect" panel in `admin_journeys.html`, methodology list, preview of generated journeys, and new actions (Explain/Improve) for existing journeys.

## Testing:
- Unit tests for `validate_journey_spec` and retry logic in `tests/test_journey_architect.py` passed.
- Attempted frontend verification but environment constraints (Docker pull limits) prevented full app startup.

## Reflections:
- The agent uses a structured JSON output with error correction loops (up to 3 attempts).
- Consistencies between `tag_mappings`, `collects_fields`, and `output_schema` are validated both in the agent and by the API.

Please review the architectural choices and the consistency of the journey structure.
