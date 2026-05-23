"""i18n updates

Revision ID: l1m2n3o4p5q6
Revises: k6l7m8n9o0p1
Create Date: 2024-05-24 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'l1m2n3o4p5q6'
down_revision = 'k6l7m8n9o0p1'
branch_labels = None
depends_on = None


def upgrade():
    # Add locale to client_shared_profiles
    op.add_column('client_shared_profiles', sa.Column('locale', sa.String(), nullable=True, server_default='es'))

    # Remove unique constraint from agent_prompts.agent
    # First, need to find the constraint name if it exists, or just drop index and recreate
    # Since it's often an implicit unique index in SQLite/Postgres
    try:
        op.drop_index('ix_agent_prompts_agent', table_name='agent_prompts')
    except:
        pass

    # Re-create index without unique
    op.create_index('ix_agent_prompts_agent', 'agent_prompts', ['agent'], unique=False)


def downgrade():
    op.drop_column('client_shared_profiles', 'locale')
    op.drop_index('ix_agent_prompts_agent', table_name='agent_prompts')
    op.create_index('ix_agent_prompts_agent', 'agent_prompts', ['agent'], unique=True)
