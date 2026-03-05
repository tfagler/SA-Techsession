"""add ingest status and education fields

Revision ID: 0002_ingest_status_and_education
Revises: 0001_initial
Create Date: 2026-03-04
"""
from alembic import op
import sqlalchemy as sa


revision = '0002_ingest_status_and_education'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('study_sessions', sa.Column('ingest_status', sa.String(length=16), nullable=False, server_default='done'))
    op.add_column('study_sessions', sa.Column('ingest_error', sa.Text(), nullable=True))
    op.add_column('study_sessions', sa.Column('ingest_started_at', sa.DateTime(), nullable=True))
    op.add_column('study_sessions', sa.Column('ingest_finished_at', sa.DateTime(), nullable=True))
    op.add_column('study_sessions', sa.Column('education_summary', sa.Text(), nullable=True))
    op.add_column('study_sessions', sa.Column('education_key_points', sa.JSON(), nullable=True))
    op.add_column('study_sessions', sa.Column('education_glossary', sa.JSON(), nullable=True))
    op.add_column('study_sessions', sa.Column('education_quiz', sa.JSON(), nullable=True))

    op.add_column('chunks', sa.Column('source_type', sa.String(length=32), nullable=False, server_default='text'))
    op.add_column('chunks', sa.Column('mime_type', sa.String(length=128), nullable=True))
    op.add_column('chunks', sa.Column('extract_method', sa.String(length=32), nullable=True))
    op.add_column('chunks', sa.Column('char_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('chunks', sa.Column('word_count', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('chunks', 'word_count')
    op.drop_column('chunks', 'char_count')
    op.drop_column('chunks', 'extract_method')
    op.drop_column('chunks', 'mime_type')
    op.drop_column('chunks', 'source_type')

    op.drop_column('study_sessions', 'education_quiz')
    op.drop_column('study_sessions', 'education_glossary')
    op.drop_column('study_sessions', 'education_key_points')
    op.drop_column('study_sessions', 'education_summary')
    op.drop_column('study_sessions', 'ingest_finished_at')
    op.drop_column('study_sessions', 'ingest_started_at')
    op.drop_column('study_sessions', 'ingest_error')
    op.drop_column('study_sessions', 'ingest_status')
