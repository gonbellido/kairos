"""add_coaches_and_coach_sessions

Revision ID: a1b2c3d4e5f6
Revises: 42478d6875fd
Create Date: 2026-04-28 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '42478d6875fd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('coaches',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('role', sa.String(), nullable=True, server_default=sa.text("'coach'")),
        sa.Column('plan', sa.String(), nullable=True, server_default=sa.text("'free'")),
        sa.Column('password_hash', sa.String(), nullable=False),
        sa.Column('salt', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_coaches_email'), 'coaches', ['email'], unique=True)
    op.create_table('coach_sessions',
        sa.Column('token', sa.String(), nullable=False),
        sa.Column('coach_id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('token')
    )
    op.create_index(op.f('ix_coach_sessions_coach_id'), 'coach_sessions', ['coach_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_coach_sessions_coach_id'), table_name='coach_sessions')
    op.drop_table('coach_sessions')
    op.drop_index(op.f('ix_coaches_email'), table_name='coaches')
    op.drop_table('coaches')
