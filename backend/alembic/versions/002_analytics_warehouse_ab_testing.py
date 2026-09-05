"""analytics warehouse, ab testing, and conversion feedback loop

Revision ID: 002_analytics
Revises: 001_baseline
Create Date: 2026-09-06 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '002_analytics'
down_revision: Union[str, None] = '001_baseline'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Analytics Events Warehouse Table
    op.create_table(
        'analytics_events',
        sa.Column('event_id', sa.String(length=64), primary_key=True),
        sa.Column('user_id', sa.String(length=64), nullable=False),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('entity_type', sa.String(length=64), nullable=False),
        sa.Column('entity_id', sa.String(length=64), nullable=False),
        sa.Column('properties', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.String(length=64), nullable=False),
    )
    op.create_index('idx_analytics_events_user_type_date', 'analytics_events', ['user_id', 'event_type', 'created_at'])

    # 2. A/B Testing Experiments Table
    op.create_table(
        'ab_experiments',
        sa.Column('experiment_id', sa.String(length=64), primary_key=True),
        sa.Column('user_id', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('variants', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=32), server_default='ACTIVE'),
        sa.Column('created_at', sa.String(length=64), nullable=False),
        sa.Column('ended_at', sa.String(length=64), nullable=True),
    )
    op.create_index('idx_ab_experiments_user', 'ab_experiments', ['user_id', 'status'])

    # 3. A/B Testing Assignments Table
    op.create_table(
        'ab_assignments',
        sa.Column('assignment_id', sa.String(length=64), primary_key=True),
        sa.Column('experiment_id', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.String(length=64), nullable=False),
        sa.Column('entity_id', sa.String(length=64), nullable=False),
        sa.Column('variant', sa.String(length=64), nullable=False),
        sa.Column('converted', sa.Boolean(), server_default='0'),
        sa.Column('converted_at', sa.String(length=64), nullable=True),
        sa.Column('assigned_at', sa.String(length=64), nullable=False),
    )
    op.create_index('idx_ab_assignments_exp_user_entity', 'ab_assignments', ['experiment_id', 'user_id', 'entity_id'])

    # 4. Conversion Signals & Dynamic Weights Table
    op.create_table(
        'conversion_signals',
        sa.Column('signal_id', sa.String(length=64), primary_key=True),
        sa.Column('user_id', sa.String(length=64), nullable=False),
        sa.Column('feature_type', sa.String(length=32), nullable=False),
        sa.Column('feature_key', sa.String(length=128), nullable=False),
        sa.Column('sample_count', sa.Integer(), server_default='0'),
        sa.Column('callback_count', sa.Integer(), server_default='0'),
        sa.Column('conversion_rate', sa.Float(), server_default='0.0'),
        sa.Column('weight_multiplier', sa.Float(), server_default='1.0'),
        sa.Column('updated_at', sa.String(length=64), nullable=False),
    )
    op.create_index('idx_conv_signals_user_feat', 'conversion_signals', ['user_id', 'feature_type', 'feature_key'])


def downgrade() -> None:
    op.drop_index('idx_conv_signals_user_feat', table_name='conversion_signals')
    op.drop_table('conversion_signals')

    op.drop_index('idx_ab_assignments_exp_user_entity', table_name='ab_assignments')
    op.drop_table('ab_assignments')

    op.drop_index('idx_ab_experiments_user', table_name='ab_experiments')
    op.drop_table('ab_experiments')

    op.drop_index('idx_analytics_events_user_type_date', table_name='analytics_events')
    op.drop_table('analytics_events')
