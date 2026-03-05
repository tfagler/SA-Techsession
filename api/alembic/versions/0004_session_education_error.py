"""add education_error on sessions

Revision ID: 0004_session_education_error
Revises: 0003_user_llm_preferences
Create Date: 2026-03-04
"""
from alembic import op
import sqlalchemy as sa


revision = '0004_session_education_error'
down_revision = '0003_user_llm_preferences'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('study_sessions', sa.Column('education_error', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('study_sessions', 'education_error')
