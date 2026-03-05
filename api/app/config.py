from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    app_name: str = 'Study Sessions API'
    database_url: str = 'mysql+asyncmy://studyapp:studyapp@mysql:3306/studyapp'
    redis_url: str = 'redis://redis:6379/0'

    jwt_secret: str = 'change-me'
    jwt_algorithm: str = 'HS256'
    jwt_expire_minutes: int = 1440

    docs_dir: str = '/data/documents'
    cors_origins: str = 'http://localhost:5173'

    local_llm_url: str = 'http://host.docker.internal:11434'
    local_llm_model: str = 'llama3.1:8b'
    local_llm_enabled: bool = False
    local_llm_context_tokens: int = 8192
    local_llm_prompt_budget_tokens: int = 6000
    local_llm_prompt_budget_chars: int = 20000
    local_llm_prompt_policy: str = 'truncate'
    crawl_depth: int = 2
    crawl_max_pages: int = 200
    crawl_max_links_per_page: int = 200
    crawl_allowed_domains: str = ''
    crawl_include_pdfs: bool = True
    crawl_include_paths: str = ''
    crawl_exclude_paths: str = ''
    crawl_respect_robots: bool = True
    crawl_concurrency: int = 4
    crawl_request_delay_ms: int = 300
    hosted_llm_url: str = ''
    hosted_llm_model: str = 'gpt-4o-mini'
    hosted_llm_api_key: str = ''
    llm_mode: str = 'auto'

    embed_dim: int = 128
    use_ollama: bool = False
    ollama_base_url: str = 'http://host.docker.internal:11434'
    ollama_model: str = 'llama3.1'
    ollama_timeout_seconds: int = 180
    ollama_timeout_connect_seconds: int = 10
    ollama_timeout_read_seconds: int = 180
    ollama_timeout_write_seconds: int = 30
    ollama_timeout_pool_seconds: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()
