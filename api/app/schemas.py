from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = 'bearer'


class UserOut(BaseModel):
    id: int
    email: EmailStr
    cheap_mode: bool
    daily_hosted_token_budget: int


class SessionCreateIn(BaseModel):
    title: str
    description: str | None = None


class SessionOut(BaseModel):
    id: int
    title: str
    description: str | None
    created_at: datetime


class SourceCreateIn(BaseModel):
    source_type: str
    url: str | None = None
    crawl_config: dict | None = None


class SourceOut(BaseModel):
    id: int
    source_type: str
    url: str | None
    title: str | None
    status: str


class SettingsUpdateIn(BaseModel):
    cheap_mode: bool | None = None
    daily_hosted_token_budget: int | None = Field(default=None, ge=1)
    use_ollama: bool | None = None
    ollama_base_url: str | None = None
    ollama_model: str | None = None
    ollama_timeout_seconds: int | None = Field(default=None, ge=5, le=300)


class QuizGenerateIn(BaseModel):
    mode: str = 'mcq'


class QuizSubmitIn(BaseModel):
    answers: list


class FlashcardReviewIn(BaseModel):
    quality: int = Field(ge=0, le=5)


class SearchIn(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=20)
