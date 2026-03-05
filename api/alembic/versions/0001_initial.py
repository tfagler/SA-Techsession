"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-03-04
"""
from alembic import op
import sqlalchemy as sa


revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('cheap_mode', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('daily_hosted_token_budget', sa.Integer(), nullable=False, server_default='20000'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    op.create_table(
        'token_usage',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('usage_date', sa.Date(), nullable=False),
        sa.Column('tokens_in', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tokens_out', sa.Integer(), nullable=False, server_default='0'),
        sa.UniqueConstraint('user_id', 'usage_date', name='uq_user_usage_date'),
    )

    op.create_table(
        'study_sessions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('last_opened_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'sources',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('study_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_type', sa.String(length=32), nullable=False),
        sa.Column('url', sa.String(length=2048), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('etag', sa.String(length=255), nullable=True),
        sa.Column('last_modified', sa.String(length=255), nullable=True),
        sa.Column('content_hash', sa.String(length=64), nullable=True),
        sa.Column('document_path', sa.String(length=1024), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('last_ingested_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_sources_content_hash', 'sources', ['content_hash'])

    op.create_table(
        'fetch_cache',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('url', sa.String(length=2048), nullable=False),
        sa.Column('etag', sa.String(length=255), nullable=True),
        sa.Column('last_modified', sa.String(length=255), nullable=True),
        sa.Column('response_hash', sa.String(length=64), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    # MySQL utf8mb4 index keys can exceed limits on very long VARCHAR columns.
    # Keep uniqueness with a prefix length that fits InnoDB key size constraints.
    op.create_index(
        'ix_fetch_cache_url',
        'fetch_cache',
        ['url'],
        unique=True,
        mysql_length={'url': 255},
    )

    op.create_table(
        'chunks',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('study_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_id', sa.Integer(), sa.ForeignKey('sources.id', ondelete='CASCADE'), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding', sa.JSON(), nullable=False),
        sa.Column('citation_url', sa.String(length=2048), nullable=True),
        sa.Column('citation_title', sa.String(length=255), nullable=True),
        sa.Column('citation_header', sa.String(length=255), nullable=True),
        sa.Column('citation_snippet', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'highlights',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('study_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('citation', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'llm_cache',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('model', sa.String(length=128), nullable=False),
        sa.Column('prompt_hash', sa.String(length=64), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('output_text', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('model', 'prompt_hash', 'content_hash', name='uq_llm_cache'),
    )

    op.create_table(
        'quizzes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('study_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('mode', sa.String(length=32), nullable=False),
        sa.Column('questions', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'quiz_attempts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('quiz_id', sa.Integer(), sa.ForeignKey('quizzes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('total', sa.Integer(), nullable=False),
        sa.Column('answers', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'flashcards',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('study_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('front', sa.Text(), nullable=False),
        sa.Column('back', sa.Text(), nullable=False),
        sa.Column('next_review_at', sa.DateTime(), nullable=False),
        sa.Column('interval_days', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('ease_factor', sa.Float(), nullable=False, server_default='2.5'),
        sa.Column('repetition', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    for table in ['flashcards', 'quiz_attempts', 'quizzes', 'llm_cache', 'highlights', 'chunks', 'fetch_cache', 'sources', 'study_sessions', 'token_usage', 'users']:
        op.drop_table(table)
