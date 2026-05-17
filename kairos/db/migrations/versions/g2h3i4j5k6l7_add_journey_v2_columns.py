"""add_journey_v2_columns

Revision ID: g2h3i4j5k6l7
Revises: g1h2i3j4k5l6
Create Date: 2026-05-01 10:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'g2h3i4j5k6l7'
down_revision: Union[str, Sequence[str], None] = 'g1h2i3j4k5l6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE journey_agents ADD COLUMN IF NOT EXISTS expects_json BOOLEAN DEFAULT FALSE;
        ALTER TABLE journey_agents ADD COLUMN IF NOT EXISTS collects_fields JSONB DEFAULT '[]';
        ALTER TABLE journey_agents ADD COLUMN IF NOT EXISTS tag_mappings JSONB DEFAULT '{}';
        ALTER TABLE client_journeys ADD COLUMN IF NOT EXISTS collected_data JSONB DEFAULT '{}';
        ALTER TABLE client_journeys ADD COLUMN IF NOT EXISTS current_phase_order INTEGER DEFAULT 1;
        ALTER TABLE journey_agents ADD COLUMN IF NOT EXISTS phase_order INTEGER DEFAULT 0;
    """)
    op.execute("""
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
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ix_journey_phases_unique_name
            ON journey_phases (journey_id, name);
    """)


def downgrade() -> None:
    pass
