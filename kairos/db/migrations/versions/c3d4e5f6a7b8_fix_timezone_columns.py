"""fix_timezone_columns

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-04-28 14:20:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('profiles', 'created_at', type_=sa.DateTime(timezone=True))
    op.alter_column('profiles', 'updated_at', type_=sa.DateTime(timezone=True))
    op.alter_column('sessions', 'created_at', type_=sa.DateTime(timezone=True))
    op.alter_column('sessions', 'updated_at', type_=sa.DateTime(timezone=True))
    op.alter_column('coaches', 'created_at', type_=sa.DateTime(timezone=True))
    op.alter_column('coach_sessions', 'created_at', type_=sa.DateTime(timezone=True))
    op.alter_column('agent_prompts', 'created_at', type_=sa.DateTime(timezone=True))
    op.alter_column('agent_prompts', 'updated_at', type_=sa.DateTime(timezone=True))


def downgrade() -> None:
    op.alter_column('profiles', 'created_at', type_=sa.DateTime())
    op.alter_column('profiles', 'updated_at', type_=sa.DateTime())
    op.alter_column('sessions', 'created_at', type_=sa.DateTime())
    op.alter_column('sessions', 'updated_at', type_=sa.DateTime())
    op.alter_column('coaches', 'created_at', type_=sa.DateTime())
    op.alter_column('coach_sessions', 'created_at', type_=sa.DateTime())
    op.alter_column('agent_prompts', 'created_at', type_=sa.DateTime())
    op.alter_column('agent_prompts', 'updated_at', type_=sa.DateTime())
