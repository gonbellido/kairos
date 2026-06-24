"""add_client_journey_turn_state

Revision ID: l7m8n9o0p1q2
Revises: k6l7m8n9o0p1
Create Date: 2026-06-24 10:00:00.000000
"""
from alembic import op

revision = 'l7m8n9o0p1q2'
down_revision = 'k6l7m8n9o0p1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Additive: turn_count tracks turns in the current agent (reset on transition);
    # objective_state stores the latest per-phase objective evaluation (populated in F2).
    op.execute("ALTER TABLE client_journeys ADD COLUMN IF NOT EXISTS turn_count INTEGER DEFAULT 0")
    op.execute("ALTER TABLE client_journeys ADD COLUMN IF NOT EXISTS objective_state JSONB DEFAULT '{}'")


def downgrade() -> None:
    op.drop_column('client_journeys', 'objective_state')
    op.drop_column('client_journeys', 'turn_count')
