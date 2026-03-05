"""crawl config and ingest metrics

Revision ID: 0005_crawl_config_and_metrics
Revises: 0004_session_education_error
Create Date: 2026-03-04
"""
from alembic import op
import sqlalchemy as sa


revision = '0005_crawl_config_and_metrics'
down_revision = '0004_session_education_error'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('sources', sa.Column('crawl_config', sa.JSON(), nullable=True))

    op.add_column('study_sessions', sa.Column('pages_fetched', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('study_sessions', sa.Column('pages_skipped', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('study_sessions', sa.Column('pdfs_fetched', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('study_sessions', sa.Column('chunks_created', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('study_sessions', sa.Column('total_chars_indexed', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('study_sessions', sa.Column('ingest_last_url', sa.String(length=2048), nullable=True))
    op.add_column('study_sessions', sa.Column('ingest_skip_reasons', sa.JSON(), nullable=True))

    op.add_column('chunks', sa.Column('content_type', sa.String(length=32), nullable=True))
    op.add_column('chunks', sa.Column('source_url', sa.String(length=2048), nullable=True))
    op.add_column('chunks', sa.Column('title', sa.String(length=255), nullable=True))
    op.add_column('chunks', sa.Column('fetched_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('chunks', 'fetched_at')
    op.drop_column('chunks', 'title')
    op.drop_column('chunks', 'source_url')
    op.drop_column('chunks', 'content_type')

    op.drop_column('study_sessions', 'ingest_skip_reasons')
    op.drop_column('study_sessions', 'ingest_last_url')
    op.drop_column('study_sessions', 'total_chars_indexed')
    op.drop_column('study_sessions', 'chunks_created')
    op.drop_column('study_sessions', 'pdfs_fetched')
    op.drop_column('study_sessions', 'pages_skipped')
    op.drop_column('study_sessions', 'pages_fetched')

    op.drop_column('sources', 'crawl_config')
