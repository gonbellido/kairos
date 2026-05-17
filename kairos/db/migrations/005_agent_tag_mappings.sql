-- Migration 005: Add tag_mappings to journey_agents (agent-level routing config)
ALTER TABLE journey_agents ADD COLUMN IF NOT EXISTS tag_mappings JSONB DEFAULT '{}';

-- Backfill existing agents from journey-level tag_mappings where applicable
-- (manual step: copy journey.tag_mappings to individual agents if needed)
