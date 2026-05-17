"""add_settings_columns

Revision ID: g1h2i3j4k5l6
Revises: f6a7b8c9d0e1
Create Date: 2026-04-29 18:30:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'g1h2i3j4k5l6'
down_revision: Union[str, Sequence[str], None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('coaches', sa.Column('notification_settings', sa.JSON(), nullable=True, server_default=sa.text("'{}'")))
    op.add_column('coaches', sa.Column('onboarding_meta', sa.JSON(), nullable=True, server_default=sa.text("'{}'")))


def downgrade() -> None:
    op.drop_column('coaches', 'onboarding_meta')
    op.drop_column('coaches', 'notification_settings')
