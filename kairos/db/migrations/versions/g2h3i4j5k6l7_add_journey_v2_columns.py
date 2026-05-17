"""Etapa 8.1: New schema — add columns without breaking existing data."""

# This migration should be run manually once against the production DB.
# It adds columns for the v2 journey engine while keeping all existing data.

SQL = """
-- Add expects_json to journey_agents (merged phase+agent concept)
ALTER TABLE journey_agents ADD COLUMN IF NOT EXISTS expects_json BOOLEAN DEFAULT FALSE;
ALTER TABLE journey_agents ADD COLUMN IF NOT EXISTS collects_fields JSONB DEFAULT '[]';
ALTER TABLE journey_agents ADD COLUMN IF NOT EXISTS tag_mappings JSONB DEFAULT '{}';

-- Add collected_data to client_journeys (accumulated across phases)
ALTER TABLE client_journeys ADD COLUMN IF NOT EXISTS collected_data JSONB DEFAULT '{}';

-- Add phase_order tracking (replaces separate phase/agent foreign keys)
ALTER TABLE client_journeys ADD COLUMN IF NOT EXISTS current_phase_order INTEGER DEFAULT 1;

-- Coach profiles: impronta variables editable from UI
CREATE TABLE IF NOT EXISTS coach_profiles (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    coach_id        TEXT NOT NULL UNIQUE REFERENCES coaches(id) ON DELETE CASCADE,
    directividad    FLOAT DEFAULT 0.5,
    emocionalidad   FLOAT DEFAULT 0.5,
    ritmo           FLOAT DEFAULT 0.5,
    coach_persona   TEXT DEFAULT '',
    default_journey_id UUID REFERENCES journeys(id),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- Add phase_order column to journey_agents for ordering within phases
ALTER TABLE journey_agents ADD COLUMN IF NOT EXISTS phase_order INTEGER DEFAULT 0;

-- Make journey_phases name unique per journey
CREATE UNIQUE INDEX IF NOT EXISTS ix_journey_phases_unique_name
    ON journey_phases (journey_id, name);
"""
