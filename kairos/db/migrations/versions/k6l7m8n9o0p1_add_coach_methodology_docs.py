"""add_coach_methodology_docs

Revision ID: k6l7m8n9o0p1
Revises: j5k6l7m8n9o0
Create Date: 2026-05-17 00:02:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'k6l7m8n9o0p1'
down_revision: Union[str, Sequence[str], None] = 'j5k6l7m8n9o0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS coach_methodology_docs (
            id TEXT PRIMARY KEY,
            coach_id TEXT NOT NULL REFERENCES coaches(id) ON DELETE CASCADE,
            title TEXT NOT NULL DEFAULT '',
            content TEXT NOT NULL,
            source TEXT DEFAULT 'text',
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_coach_methodology_docs_coach_id ON coach_methodology_docs (coach_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS coach_methodology_docs")
