"""add_journey_transitions

Revision ID: m7n8o9p0q1r2
Revises: l7m8n9o0p1q2
Create Date: 2026-06-24 11:00:00.000000
"""
from alembic import op

revision = 'm7n8o9p0q1r2'
down_revision = 'l7m8n9o0p1q2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS journey_transitions (
            id              TEXT PRIMARY KEY,
            journey_id      TEXT NOT NULL REFERENCES journeys(id) ON DELETE CASCADE,
            from_phase_id   TEXT NOT NULL,
            to_phase_id     TEXT DEFAULT '',
            condition       JSONB DEFAULT '{}',
            priority        INTEGER DEFAULT 0,
            is_active       BOOLEAN DEFAULT TRUE,
            created_at      TIMESTAMPTZ DEFAULT now(),
            updated_at      TIMESTAMPTZ DEFAULT now()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_journey_transitions_journey_id ON journey_transitions (journey_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_journey_transitions_from_phase_id ON journey_transitions (from_phase_id)")


def downgrade() -> None:
    op.drop_table('journey_transitions')
