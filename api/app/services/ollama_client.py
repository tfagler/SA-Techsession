import logging
import time
import asyncio
from urllib.parse import urljoin, urlsplit, urlunsplit
import httpx
from app.config import get_settings


logger = logging.getLogger(__name__)
settings = get_settings()
_probed_bases: set[str] = set()
_base_models_cache: dict[str, set[str]] = {}


def normalize_ollama_base_url(raw_base: str) -> str:
    candidate = (raw_base or '').strip() or settings.ollama_base_url
    parts = urlsplit(candidate)
    scheme = parts.scheme or 'http'
    netloc = parts.netloc
    path = parts.path.rstrip('/')

    if path.lower().endswith('/api'):
        path = path[:-4]

    normalized = urlunsplit((scheme, netloc, path, '', ''))
    return normalized.rstrip('/')


def build_ollama_endpoints(base_url: str) -> tuple[str, str]:
    base = normalize_ollama_base_url(base_url)
    base_slash = f'{base}/'
    return (
        urljoin(base_slash, 'api/generate'),
        urljoin(base_slash, 'api/chat'),
    )


def _payload_debug(payload: dict) -> dict:
    return {
        'model': payload.get('model'),
        'stream': payload.get('stream'),
        'prompt_length': len(str(payload.get('prompt', ''))),
    }


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _timeout_config(read_timeout_seconds: int | None = None) -> httpx.Timeout:
    read_value = read_timeout_seconds or settings.ollama_timeout_read_seconds or settings.ollama_timeout_seconds
    return httpx.Timeout(
        connect=settings.ollama_timeout_connect_seconds,
        read=read_value,
        write=settings.ollama_timeout_write_seconds,
        pool=settings.ollama_timeout_pool_seconds,
    )


def enforce_prompt_budget(prompt: str) -> str:
    budget = max(128, settings.local_llm_prompt_budget_tokens)
    char_budget = max(512, settings.local_llm_prompt_budget_chars)
    estimated = estimate_tokens(prompt)
    if estimated <= budget and len(prompt) <= char_budget:
        return prompt

    if settings.local_llm_prompt_policy.lower() == 'reject':
        raise ValueError(
            f'Prompt exceeds budget: estimated_tokens={estimated} token_budget={budget} '
            f'char_len={len(prompt)} char_budget={char_budget}. '
            'Reduce source size or increase LOCAL_LLM_PROMPT_BUDGET_TOKENS.'
        )

    words = prompt.split()
    keep_ratio = min(
        budget / max(1, estimated),
        char_budget / max(1, len(prompt)),
    )
    keep_words = max(32, int(len(words) * keep_ratio))
    truncated = ' '.join(words[:keep_words]) if words else prompt[: budget * 4]
    while (estimate_tokens(truncated) > budget or len(truncated) > char_budget) and len(truncated) > 64:
        truncated = truncated[: int(len(truncated) * 0.9)]
    logger.warning(
        'ollama.prompt truncated estimated_tokens=%d token_budget=%d char_len=%d char_budget=%d resulting_tokens=%d resulting_chars=%d',
        estimated,
        budget,
        len(prompt),
        char_budget,
        estimate_tokens(truncated),
        len(truncated),
    )
    return truncated


async def _send_json_with_debug(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    payload: dict,
) -> httpx.Response:
    headers = {'Content-Type': 'application/json'}
    request = client.build_request(method, url, json=payload, headers=headers)
    logger.info(
        'ollama.request method=%s url=%s payload=%s',
        request.method,
        str(request.url),
        _payload_debug(payload),
    )
    response = await client.send(request)
    if response.status_code >= 400:
        logger.warning(
            'ollama.response error status=%d url=%s body=%s',
            response.status_code,
            str(request.url),
            response.text[:300],
        )
    return response


async def probe_ollama(base_url: str, timeout_seconds: int) -> set[str]:
    if base_url in _probed_bases and base_url in _base_models_cache:
        return _base_models_cache[base_url]

    if base_url in _probed_bases:
        return _base_models_cache.get(base_url, set())
    version_url = urljoin(f'{base_url}/', 'api/version')
    tags_url = urljoin(f'{base_url}/', 'api/tags')
    async with httpx.AsyncClient(timeout=_timeout_config(timeout_seconds)) as client:
        version_resp = await client.get(version_url)
        tags_resp = await client.get(tags_url)
    version_resp.raise_for_status()
    tags_resp.raise_for_status()
    tags_payload = tags_resp.json() if tags_resp.content else {}
    models = set()
    for item in tags_payload.get('models', []):
        if isinstance(item, dict):
            if item.get('name'):
                models.add(str(item['name']))
            if item.get('model'):
                models.add(str(item['model']))
    _base_models_cache[base_url] = models
    _probed_bases.add(base_url)
    logger.info('ollama.probe ok base=%s version_url=%s tags_url=%s models=%d', base_url, version_url, tags_url, len(models))
    return models


def _pick_model(requested_model: str | None, available: set[str]) -> str:
    if requested_model and requested_model in available:
        return requested_model
    if requested_model and requested_model not in available:
        preview = ', '.join(sorted(list(available))[:12]) or '(none)'
        raise ValueError(
            f"Ollama model '{requested_model}' not found. Available: {preview}. "
            "Set LOCAL_LLM_MODEL to an available model or update user settings."
        )
    if 'llama3:latest' in available:
        return 'llama3:latest'
    preview = ', '.join(sorted(list(available))[:12]) or '(none)'
    raise ValueError(
        f'No requested model provided and fallback llama3:latest not found. Available: {preview}. '
        'Set LOCAL_LLM_MODEL or user model preference.'
    )


async def ollama_generate(
    prompt: str,
    base_url: str | None = None,
    model: str | None = None,
    timeout_seconds: int | None = None,
) -> str:
    base = normalize_ollama_base_url(base_url or settings.ollama_base_url)
    requested_model = model or settings.local_llm_model
    timeout = timeout_seconds or settings.ollama_timeout_read_seconds or settings.ollama_timeout_seconds
    generate_url, chat_url = build_ollama_endpoints(base)
    available_models = await probe_ollama(base, timeout)
    use_model = _pick_model(requested_model, available_models)
    prompt = enforce_prompt_budget(prompt)
    estimated_tokens = estimate_tokens(prompt)
    timeout_cfg = _timeout_config(timeout)
    logger.info(
        'ollama.generate config model=%s endpoint=%s final_prompt_char_len=%d estimated_token_len=%d timeout_connect=%.1f timeout_read=%.1f timeout_write=%.1f timeout_pool=%.1f',
        use_model,
        generate_url,
        len(prompt),
        estimated_tokens,
        timeout_cfg.connect,
        timeout_cfg.read,
        timeout_cfg.write,
        timeout_cfg.pool,
    )

    last_exc: Exception | None = None
    backoffs = [0.3, 0.8, 1.6]
    for attempt, backoff in enumerate(backoffs, start=1):
        started = time.perf_counter()
        try:
            generate_payload = {'model': use_model, 'prompt': prompt, 'stream': False}
            async with httpx.AsyncClient(timeout=_timeout_config(timeout)) as client:
                response = await _send_json_with_debug(
                    client=client,
                    method='POST',
                    url=generate_url,
                    payload=generate_payload,
                )

                # Fallback for Ollama variants that may not expose /api/generate.
                if response.status_code == 404:
                    chat_payload = {
                        'model': use_model,
                        'stream': False,
                        'messages': [
                            {'role': 'user', 'content': prompt},
                        ],
                    }
                    response = await _send_json_with_debug(
                        client=client,
                        method='POST',
                        url=chat_url,
                        payload=chat_payload,
                    )

            response.raise_for_status()
            payload = response.json() if response.content else {}
            latency_ms = (time.perf_counter() - started) * 1000
            text = str(payload.get('response', '')).strip()
            if not text:
                msg = payload.get('message')
                if isinstance(msg, dict):
                    text = str(msg.get('content', '')).strip()
            logger.info(
                'ollama.generate endpoint=%s model=%s latency_ms=%.1f prompt_chars=%d response_chars=%d attempt=%d',
                generate_url,
                use_model,
                latency_ms,
                len(prompt),
                len(text),
                attempt,
            )
            return text
        except Exception as exc:
            last_exc = exc
            logger.warning(
                'ollama.generate failed endpoint=%s attempt=%d error_type=%s error_repr=%s',
                generate_url,
                attempt,
                type(exc).__name__,
                repr(exc),
            )
            if attempt < len(backoffs):
                await asyncio.sleep(backoff)

    if last_exc:
        raise last_exc
    raise RuntimeError('Ollama generate failed without explicit exception')
