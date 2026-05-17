"""add_journey_tag_version

Revision ID: h3i4j5k6l7m8
Revises: g2h3i4j5k6l7
Create Date: 2026-05-17 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'h3i4j5k6l7m8'
down_revision: Union[str, Sequence[str], None] = 'g2h3i4j5k6l7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('journeys', sa.Column('tag_mappings', sa.JSON(), nullable=True, server_default=sa.text("'{}'")) )
    op.add_column('journeys', sa.Column('version', sa.Integer(), nullable=True, server_default='1'))


def downgrade() -> None:
    op.drop_column('journeys', 'version')
    op.drop_column('journeys', 'tag_mappings')
