"""add_missing_coach_columns

Revision ID: i4j5k6l7m8n9
Revises: h3i4j5k6l7m8
Create Date: 2026-05-17 00:01:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'i4j5k6l7m8n9'
down_revision: Union[str, Sequence[str], None] = 'h3i4j5k6l7m8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('coaches', sa.Column('telegram_bot_name', sa.String(), nullable=True, server_default="''"))
    op.add_column('coaches', sa.Column('impronta_data', sa.JSON(), nullable=True, server_default=sa.text("'{}'")) )
    op.add_column('coaches', sa.Column('profile_data', sa.JSON(), nullable=True, server_default=sa.text("'{}'")) )
    op.add_column('coaches', sa.Column('default_journey_id', sa.String(), nullable=True, server_default="''"))


def downgrade() -> None:
    op.drop_column('coaches', 'default_journey_id')
    op.drop_column('coaches', 'profile_data')
    op.drop_column('coaches', 'impronta_data')
    op.drop_column('coaches', 'telegram_bot_name')
