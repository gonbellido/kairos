"""add_journey_agent_missing_cols

Revision ID: j5k6l7m8n9o0
Revises: i4j5k6l7m8n9
Create Date: 2026-05-18 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'j5k6l7m8n9o0'
down_revision = 'i4j5k6l7m8n9'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Use individual execute calls for asyncpg compatibility
    # Postgres specific ADD COLUMN IF NOT EXISTS
    op.execute("ALTER TABLE journey_agents ADD COLUMN IF NOT EXISTS allowed_tags JSON DEFAULT '[]'")
    op.execute("ALTER TABLE journey_agents ADD COLUMN IF NOT EXISTS output_schema JSON DEFAULT '{}'")
    op.execute("ALTER TABLE journey_agents ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1")

def downgrade() -> None:
    op.drop_column('journey_agents', 'version')
    op.drop_column('journey_agents', 'output_schema')
    op.drop_column('journey_agents', 'allowed_tags')
