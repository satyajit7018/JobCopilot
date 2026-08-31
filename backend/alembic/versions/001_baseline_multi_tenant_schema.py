"""baseline multi-tenant schema

Revision ID: 001_baseline
Revises: 
Create Date: 2026-08-31 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '001_baseline'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Users Table
    op.create_table(
        'users',
        sa.Column('user_id', sa.String(length=64), primary_key=True),
        sa.Column('email', sa.String(length=255), nullable=False, unique=True),
        sa.Column('password_hash', sa.Text(), nullable=False),
        sa.Column('full_name', sa.String(length=255), server_default=''),
        sa.Column('role', sa.String(length=32), server_default='FREE'),
        sa.Column('is_active', sa.Boolean(), server_default='1'),
        sa.Column('email_verified', sa.Boolean(), server_default='0'),
        sa.Column('created_at', sa.String(length=64), nullable=False),
        sa.Column('updated_at', sa.String(length=64), nullable=False),
    )
    op.create_index('idx_users_email', 'users', ['email'])

    # 2. Profiles Table
    op.create_table(
        'profiles',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('user_id', sa.String(length=64), nullable=False, server_default='default'),
        sa.Column('data', sa.JSON(), nullable=False),
        sa.Column('updated_at', sa.String(length=64), nullable=False),
    )
    op.create_index('idx_profiles_user_id', 'profiles', ['user_id'])

    # 3. Vault Table
    op.create_table(
        'vault',
        sa.Column('qa_id', sa.String(length=64), primary_key=True),
        sa.Column('user_id', sa.String(length=64), nullable=False, server_default='default'),
        sa.Column('slot_type', sa.String(length=64), nullable=False),
        sa.Column('slot_key', sa.String(length=128), nullable=False),
        sa.Column('question_pattern', sa.Text(), nullable=False),
        sa.Column('embedding', sa.JSON(), nullable=False),
        sa.Column('answer_template', sa.Text(), nullable=False),
        sa.Column('dynamic_variables', sa.JSON(), nullable=False),
        sa.Column('usage_count', sa.Integer(), server_default='0'),
        sa.Column('last_used_at', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.String(length=64), nullable=False),
    )
    op.create_index('idx_vault_user_slot', 'vault', ['user_id', 'slot_key'])

    # 4. Jobs Table
    op.create_table(
        'jobs',
        sa.Column('job_id', sa.String(length=64), primary_key=True),
        sa.Column('user_id', sa.String(length=64), nullable=False, server_default='default'),
        sa.Column('fingerprint', sa.String(length=128), nullable=False),
        sa.Column('platform', sa.String(length=64), nullable=False),
        sa.Column('company', sa.String(length=255), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('location', sa.String(length=255), server_default='Remote / India'),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), server_default=''),
        sa.Column('salary_range', sa.String(length=128), nullable=True),
        sa.Column('seniority_level', sa.String(length=64), nullable=True),
        sa.Column('posted_date', sa.String(length=64), nullable=True),
        sa.Column('match_score', sa.Float(), server_default='0.0'),
        sa.Column('priority_score', sa.Float(), server_default='0.0'),
        sa.Column('match_reasons', sa.JSON(), nullable=True),
        sa.Column('missing_skills', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=64), nullable=False),
        sa.Column('submission_mode', sa.String(length=32), nullable=True),
        sa.Column('applied_at', sa.String(length=64), nullable=True),
        sa.Column('application_id', sa.String(length=128), nullable=True),
        sa.Column('confirmation_screenshot_path', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
    )
    op.create_index('idx_jobs_user_status', 'jobs', ['user_id', 'status'])


def downgrade() -> None:
    op.drop_table('jobs')
    op.drop_table('vault')
    op.drop_table('profiles')
    op.drop_table('users')
