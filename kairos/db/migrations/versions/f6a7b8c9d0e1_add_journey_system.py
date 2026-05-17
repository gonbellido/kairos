"""add_journey_system

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-04-29 14:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('journeys',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('coach_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True, server_default=''),
        sa.Column('objective', sa.Text(), nullable=True, server_default=''),
        sa.Column('profile_type', sa.String(), nullable=True, server_default='custom'),
        sa.Column('language', sa.String(), nullable=True, server_default='es'),
        sa.Column('status', sa.String(), nullable=True, server_default='draft'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_journeys_coach_id', 'journeys', ['coach_id'])

    op.create_table('journey_phases',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('journey_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True, server_default=''),
        sa.Column('objective', sa.Text(), nullable=True, server_default=''),
        sa.Column('order_index', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('completion_criteria', sa.Text(), nullable=True, server_default=''),
        sa.Column('visible_to_client', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_journey_phases_journey_id', 'journey_phases', ['journey_id'])

    op.create_table('journey_agents',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('journey_id', sa.String(), nullable=False),
        sa.Column('phase_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('role', sa.String(), nullable=True, server_default=''),
        sa.Column('goal', sa.Text(), nullable=True, server_default=''),
        sa.Column('system_prompt', sa.Text(), nullable=True, server_default=''),
        sa.Column('instructions', sa.Text(), nullable=True, server_default=''),
        sa.Column('order_index', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_journey_agents_journey_id', 'journey_agents', ['journey_id'])
    op.create_index('ix_journey_agents_phase_id', 'journey_agents', ['phase_id'])

    op.create_table('client_journeys',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('client_id', sa.String(), nullable=False),
        sa.Column('coach_id', sa.String(), nullable=False),
        sa.Column('journey_id', sa.String(), nullable=False),
        sa.Column('current_phase_id', sa.String(), nullable=True),
        sa.Column('current_agent_id', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True, server_default='not_started'),
        sa.Column('progress_pct', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('extra', sa.JSON(), nullable=True, server_default=sa.text("'{}'")),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_interaction_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_client_journeys_client_id', 'client_journeys', ['client_id'])
    op.create_index('ix_client_journeys_coach_id', 'client_journeys', ['coach_id'])

    op.create_table('client_shared_profiles',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('client_id', sa.String(), nullable=False),
        sa.Column('coach_id', sa.String(), nullable=False),
        sa.Column('journey_id', sa.String(), nullable=True),
        sa.Column('profile_data', sa.JSON(), nullable=True, server_default=sa.text("'{}'")),
        sa.Column('goals_data', sa.JSON(), nullable=True, server_default=sa.text("'{}'")),
        sa.Column('insights_data', sa.JSON(), nullable=True, server_default=sa.text("'[]'")),
        sa.Column('blockers_data', sa.JSON(), nullable=True, server_default=sa.text("'[]'")),
        sa.Column('tasks_data', sa.JSON(), nullable=True, server_default=sa.text("'[]'")),
        sa.Column('checkpoints_data', sa.JSON(), nullable=True, server_default=sa.text("'[]'")),
        sa.Column('conversation_summary', sa.Text(), nullable=True, server_default=''),
        sa.Column('risk_flags_data', sa.JSON(), nullable=True, server_default=sa.text("'[]'")),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_client_shared_profiles_client_id', 'client_shared_profiles', ['client_id'], unique=True)
    op.create_index('ix_client_shared_profiles_coach_id', 'client_shared_profiles', ['coach_id'])

    op.create_table('journey_events',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('client_id', sa.String(), nullable=False),
        sa.Column('coach_id', sa.String(), nullable=False),
        sa.Column('journey_id', sa.String(), nullable=True),
        sa.Column('phase_id', sa.String(), nullable=True),
        sa.Column('agent_id', sa.String(), nullable=True),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('payload_data', sa.JSON(), nullable=True, server_default=sa.text("'{}'")),
        sa.Column('trace_id', sa.String(), nullable=True, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_journey_events_client_id', 'journey_events', ['client_id'])


def downgrade() -> None:
    op.drop_table('journey_events')
    op.drop_table('client_shared_profiles')
    op.drop_table('client_journeys')
    op.drop_table('journey_agents')
    op.drop_table('journey_phases')
    op.drop_table('journeys')
