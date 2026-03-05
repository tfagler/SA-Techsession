import hashlib
from datetime import date
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import get_settings
from app.models import LLMCache, TokenUsage, User


settings = get_settings()


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


async def _usage_for_today(db: AsyncSession, user_id: int) -> TokenUsage:
    result = await db.execute(
        select(TokenUsage).where(TokenUsage.user_id == user_id, TokenUsage.usage_date == date.today())
    )
    row = result.scalar_one_or_none()
    if row:
        return row
    row = TokenUsage(user_id=user_id, usage_date=date.today(), tokens_in=0, tokens_out=0)
    db.add(row)
    await db.flush()
    return row


async def _call_local(prompt: str) -> str:
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{settings.local_llm_url.rstrip('/')}/api/generate",
            json={"model": settings.local_llm_model, "prompt": prompt, "stream": False},
        )
    resp.raise_for_status()
    data = resp.json()
    return data.get('response', '').strip() or 'No output.'


async def _call_hosted(prompt: str) -> str:
    if not settings.hosted_llm_url:
        return 'Hosted provider not configured. Falling back content unavailable.'
    headers = {'Content-Type': 'application/json'}
    if settings.hosted_llm_api_key:
        headers['Authorization'] = f'Bearer {settings.hosted_llm_api_key}'
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            settings.hosted_llm_url,
            json={'model': settings.hosted_llm_model, 'prompt': prompt},
            headers=headers,
        )
    resp.raise_for_status()
    data = resp.json()
    return str(data.get('text') or data.get('output') or data)


async def run_llm(
    db: AsyncSession,
    user: User,
    prompt: str,
    content_hash: str,
    requested_mode: str | None = None,
) -> str:
    mode = (requested_mode or settings.llm_mode).lower()
    prompt_hash = hashlib.sha256(prompt.encode('utf-8')).hexdigest()

    model = settings.local_llm_model if mode == 'local' else settings.hosted_llm_model
    result = await db.execute(
        select(LLMCache).where(
            LLMCache.model == model,
            LLMCache.prompt_hash == prompt_hash,
            LLMCache.content_hash == content_hash,
        )
    )
    cached = result.scalar_one_or_none()
    if cached:
        return cached.output_text

    usage = await _usage_for_today(db, user.id)
    hosted_used = usage.tokens_in + usage.tokens_out
    hosted_allowed = hosted_used < user.daily_hosted_token_budget

    run_mode = mode
    if mode == 'auto':
        if user.cheap_mode or not hosted_allowed:
            run_mode = 'local'
        else:
            run_mode = 'hosted'

    if run_mode == 'hosted' and not hosted_allowed:
        raise ValueError('Daily hosted token budget exceeded')

    if run_mode == 'local':
        output = await _call_local(prompt)
        model = settings.local_llm_model
    else:
        output = await _call_hosted(prompt)
        model = settings.hosted_llm_model
        usage.tokens_in += estimate_tokens(prompt)
        usage.tokens_out += estimate_tokens(output)

    db.add(
        LLMCache(model=model, prompt_hash=prompt_hash, content_hash=content_hash, output_text=output)
    )
    await db.commit()
    return output
