"""compliance and user consent management
Revision ID: 003_compliance
Revises: 002_analytics
Create Date: 2026-09-06 04:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '003_compliance'
down_revision: Union[str, None] = '002_analytics'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. User Consents Audit Table
    op.create_table(
        'user_consents',
        sa.Column('consent_id', sa.String(length=64), primary_key=True),
        sa.Column('user_id', sa.String(length=64), nullable=False),
        sa.Column('consent_type', sa.String(length=64), nullable=False),
        sa.Column('version', sa.String(length=32), nullable=False, server_default='1.0'),
        sa.Column('consented', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('ip_address', sa.String(length=64), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('created_at', sa.String(length=64), nullable=False),
    )
    op.create_index('idx_user_consents_user_type', 'user_consents', ['user_id', 'consent_type'])
    op.create_index('idx_user_consents_user_created', 'user_consents', ['user_id', 'created_at'])


def downgrade() -> None:
    op.drop_table('user_consents')
