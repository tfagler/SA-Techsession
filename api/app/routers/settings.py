from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.deps import get_current_user
from app.models import TokenUsage, User
from app.schemas import SettingsUpdateIn


router = APIRouter(prefix='/settings', tags=['settings'])


def _effective_local_llm(user: User) -> dict:
    from app.config import get_settings

    settings = get_settings()

    enabled = user.use_ollama if user.use_ollama is not None else settings.local_llm_enabled
    enabled_source = 'user_pref' if user.use_ollama is not None else 'env_default'

    url_value = user.ollama_base_url or settings.local_llm_url or settings.ollama_base_url
    if user.ollama_base_url:
        url_source = 'user_pref'
    elif settings.local_llm_url:
        url_source = 'env_default'
    else:
        url_source = 'fallback'

    model_value = user.ollama_model or settings.local_llm_model or settings.ollama_model
    if user.ollama_model:
        model_source = 'user_pref'
    elif settings.local_llm_model:
        model_source = 'env_default'
    else:
        model_source = 'fallback'

    timeout_value = user.ollama_timeout_seconds or settings.ollama_timeout_read_seconds or settings.ollama_timeout_seconds
    timeout_source = 'user_pref' if user.ollama_timeout_seconds else 'env_default'

    return {
        'local_llm_enabled': enabled,
        'local_llm_url_effective': url_value,
        'local_llm_model_effective': model_value,
        'local_llm_timeout_seconds_effective': timeout_value,
        'local_llm_source': {
            'enabled': enabled_source,
            'url': url_source,
            'model': model_source,
            'timeout_seconds': timeout_source,
        },
    }


def _crawl_defaults() -> dict:
    from app.config import get_settings

    settings = get_settings()
    return {
        'crawl_depth': settings.crawl_depth,
        'max_pages': settings.crawl_max_pages,
        'max_links_per_page': settings.crawl_max_links_per_page,
        'allowed_domains': [d.strip() for d in settings.crawl_allowed_domains.split(',') if d.strip()],
        'include_pdfs': settings.crawl_include_pdfs,
        'include_paths': settings.crawl_include_paths,
        'exclude_paths': settings.crawl_exclude_paths,
        'respect_robots': settings.crawl_respect_robots,
        'concurrency': settings.crawl_concurrency,
        'request_delay_ms': settings.crawl_request_delay_ms,
    }


@router.get('')
async def get_settings_route(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    usage_result = await db.execute(
        select(TokenUsage).where(TokenUsage.user_id == user.id, TokenUsage.usage_date == date.today())
    )
    usage = usage_result.scalar_one_or_none()
    effective = _effective_local_llm(user)
    return {
        'cheap_mode': user.cheap_mode,
        'daily_hosted_token_budget': user.daily_hosted_token_budget,
        'use_ollama': user.use_ollama,
        'ollama_base_url': user.ollama_base_url,
        'ollama_model': user.ollama_model,
        'ollama_timeout_seconds': user.ollama_timeout_seconds,
        'today_tokens_in': usage.tokens_in if usage else 0,
        'today_tokens_out': usage.tokens_out if usage else 0,
        'crawl_defaults': _crawl_defaults(),
        **effective,
    }


@router.put('')
async def update_settings(payload: SettingsUpdateIn, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    if payload.cheap_mode is not None:
        user.cheap_mode = payload.cheap_mode
    if payload.daily_hosted_token_budget is not None:
        user.daily_hosted_token_budget = payload.daily_hosted_token_budget
    if payload.use_ollama is not None:
        user.use_ollama = payload.use_ollama
    if payload.ollama_base_url is not None:
        user.ollama_base_url = payload.ollama_base_url
    if payload.ollama_model is not None:
        user.ollama_model = payload.ollama_model
    if payload.ollama_timeout_seconds is not None:
        user.ollama_timeout_seconds = payload.ollama_timeout_seconds
    await db.commit()
    effective = _effective_local_llm(user)
    return {
        'cheap_mode': user.cheap_mode,
        'daily_hosted_token_budget': user.daily_hosted_token_budget,
        'use_ollama': user.use_ollama,
        'ollama_base_url': user.ollama_base_url,
        'ollama_model': user.ollama_model,
        'ollama_timeout_seconds': user.ollama_timeout_seconds,
        'crawl_defaults': _crawl_defaults(),
        **effective,
    }
