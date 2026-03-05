from datetime import datetime, date
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, Boolean, UniqueConstraint, Date, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.mysql import JSON
from app.database import Base


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    cheap_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    daily_hosted_token_budget: Mapped[int] = mapped_column(Integer, default=20000)
    use_ollama: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    ollama_base_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ollama_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ollama_timeout_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TokenUsage(Base):
    __tablename__ = 'token_usage'
    __table_args__ = (UniqueConstraint('user_id', 'usage_date', name='uq_user_usage_date'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    usage_date: Mapped[date] = mapped_column(Date, default=date.today)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)


class StudySession(Base):
    __tablename__ = 'study_sessions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_opened_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ingest_status: Mapped[str] = mapped_column(String(16), default='done')
    ingest_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingest_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ingest_finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    education_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    pages_fetched: Mapped[int] = mapped_column(Integer, default=0)
    pages_skipped: Mapped[int] = mapped_column(Integer, default=0)
    pdfs_fetched: Mapped[int] = mapped_column(Integer, default=0)
    chunks_created: Mapped[int] = mapped_column(Integer, default=0)
    total_chars_indexed: Mapped[int] = mapped_column(Integer, default=0)
    ingest_last_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    ingest_skip_reasons: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    education_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    education_key_points: Mapped[list | None] = mapped_column(JSON, nullable=True)
    education_glossary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    education_quiz: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Source(Base):
    __tablename__ = 'sources'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey('study_sessions.id', ondelete='CASCADE'), index=True)
    source_type: Mapped[str] = mapped_column(String(32))
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default='pending')
    etag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_modified: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    document_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    crawl_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_ingested_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FetchCache(Base):
    __tablename__ = 'fetch_cache'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(String(2048), unique=True)
    etag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_modified: Mapped[str | None] = mapped_column(String(255), nullable=True)
    response_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Chunk(Base):
    __tablename__ = 'chunks'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey('study_sessions.id', ondelete='CASCADE'), index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey('sources.id', ondelete='CASCADE'), index=True)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list] = mapped_column(JSON)
    source_type: Mapped[str] = mapped_column(String(32), default='text')
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    extract_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    citation_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    citation_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    citation_header: Mapped[str | None] = mapped_column(String(255), nullable=True)
    citation_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Highlight(Base):
    __tablename__ = 'highlights'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey('study_sessions.id', ondelete='CASCADE'), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    text: Mapped[str] = mapped_column(Text)
    citation: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class LLMCache(Base):
    __tablename__ = 'llm_cache'
    __table_args__ = (UniqueConstraint('model', 'prompt_hash', 'content_hash', name='uq_llm_cache'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model: Mapped[str] = mapped_column(String(128), index=True)
    prompt_hash: Mapped[str] = mapped_column(String(64), index=True)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    output_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Quiz(Base):
    __tablename__ = 'quizzes'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey('study_sessions.id', ondelete='CASCADE'), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    mode: Mapped[str] = mapped_column(String(32))
    questions: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class QuizAttempt(Base):
    __tablename__ = 'quiz_attempts'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quiz_id: Mapped[int] = mapped_column(ForeignKey('quizzes.id', ondelete='CASCADE'), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    score: Mapped[float] = mapped_column(Float)
    total: Mapped[int] = mapped_column(Integer)
    answers: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Flashcard(Base):
    __tablename__ = 'flashcards'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey('study_sessions.id', ondelete='CASCADE'), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    front: Mapped[str] = mapped_column(Text)
    back: Mapped[str] = mapped_column(Text)
    next_review_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    interval_days: Mapped[int] = mapped_column(Integer, default=1)
    ease_factor: Mapped[float] = mapped_column(Float, default=2.5)
    repetition: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
