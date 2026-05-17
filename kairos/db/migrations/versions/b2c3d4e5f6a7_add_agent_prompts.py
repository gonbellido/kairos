"""add_agent_prompts

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-28 14:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('agent_prompts',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('agent', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True, server_default=''),
        sa.Column('prompt_template', sa.Text(), nullable=False),
        sa.Column('lang', sa.String(), nullable=True, server_default='es'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_agent_prompts_agent'), 'agent_prompts', ['agent'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_agent_prompts_agent'), table_name='agent_prompts')
    op.drop_table('agent_prompts')
