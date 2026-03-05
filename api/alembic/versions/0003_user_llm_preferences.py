"""add user llm preference fields

Revision ID: 0003_user_llm_preferences
Revises: 0002_ingest_status_and_education
Create Date: 2026-03-04
"""
from alembic import op
import sqlalchemy as sa


revision = '0003_user_llm_preferences'
down_revision = '0002_ingest_status_and_education'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('use_ollama', sa.Boolean(), nullable=True))
    op.add_column('users', sa.Column('ollama_base_url', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('ollama_model', sa.String(length=128), nullable=True))
    op.add_column('users', sa.Column('ollama_timeout_seconds', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'ollama_timeout_seconds')
    op.drop_column('users', 'ollama_model')
    op.drop_column('users', 'ollama_base_url')
    op.drop_column('users', 'use_ollama')
