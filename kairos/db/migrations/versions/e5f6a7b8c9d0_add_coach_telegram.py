"""add_coach_telegram

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-04-29 10:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('coaches', sa.Column('telegram_token', sa.String(), nullable=True, server_default=''))
    op.add_column('coaches', sa.Column('telegram_chat_id', sa.String(), nullable=True, server_default=''))


def downgrade() -> None:
    op.drop_column('coaches', 'telegram_chat_id')
    op.drop_column('coaches', 'telegram_token')
