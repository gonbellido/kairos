"""add_agent_fallback

Revision ID: n7o8p9q0r1s2
Revises: m7n8o9p0q1r2
Create Date: 2026-06-24 11:30:00.000000
"""
from alembic import op

revision = 'n7o8p9q0r1s2'
down_revision = 'm7n8o9p0q1r2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE journey_agents ADD COLUMN IF NOT EXISTS max_turns INTEGER DEFAULT 0")
    op.execute("ALTER TABLE journey_agents ADD COLUMN IF NOT EXISTS fallback_agent_id TEXT DEFAULT ''")


def downgrade() -> None:
    op.drop_column('journey_agents', 'fallback_agent_id')
    op.drop_column('journey_agents', 'max_turns')
