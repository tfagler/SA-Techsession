import json
import re
from collections import Counter
from app.config import get_settings
from app.models import User
from app.services.ollama_client import ollama_generate
from app.services.text_cleaning import clean_text, is_quality_chunk


settings = get_settings()


def _extract_json(text: str) -> dict | None:
    start = text.find('{')
    end = text.rfind('}')
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def _local_summary(chunks: list[str]) -> dict:
    merged = ' '.join(chunks)
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', merged) if s.strip()]
    key_points = sentences[:5] or [merged[:200]]

    words = [w for w in re.findall(r'[A-Za-z][A-Za-z\-]{4,}', merged) if w[0].isupper()]
    common = [w for w, _ in Counter(words).most_common(5)]
    glossary = {w: f'Key concept mentioned in the source material: {w}.' for w in common}

    quiz = []
    for i, kp in enumerate(key_points[:5], start=1):
        base = kp[:140]
        quiz.append(
            {
                'id': i,
                'question': f'Which option best reflects this point: {base}?',
                'options': [base, 'A contradictory statement', 'An unrelated detail', 'Not discussed'],
                'answer_index': 0,
                'explanation': 'The first option restates the extracted key point.',
            }
        )

    return {
        'summary': ' '.join(sentences[:2])[:400] if sentences else merged[:400],
        'key_points': key_points[:5],
        'glossary': glossary,
        'quiz': quiz,
    }


def _sanitize_payload(payload: dict, fallback: dict) -> dict:
    summary = clean_text(str(payload.get('summary', fallback['summary'])))[:1000]

    key_points = payload.get('key_points')
    if not isinstance(key_points, list):
        key_points = fallback['key_points']
    clean_points = []
    for item in key_points:
        text = clean_text(str(item))
        ok, _ = is_quality_chunk(text)
        if ok:
            clean_points.append(text[:300])
    if not clean_points:
        clean_points = fallback['key_points']

    glossary_in = payload.get('glossary')
    if isinstance(glossary_in, dict):
        glossary = {clean_text(str(k))[:80]: clean_text(str(v))[:300] for k, v in glossary_in.items() if str(k).strip()}
    else:
        glossary = fallback['glossary']

    quiz_in = payload.get('quiz')
    clean_quiz = []
    if isinstance(quiz_in, list):
        for i, q in enumerate(quiz_in[:6], start=1):
            if not isinstance(q, dict):
                continue
            question = clean_text(str(q.get('question', '')))
            options = q.get('options', [])
            if not isinstance(options, list):
                continue
            options = [clean_text(str(opt))[:180] for opt in options[:4]]
            if len(options) < 2:
                continue
            answer_index = q.get('answer_index', 0)
            if not isinstance(answer_index, int) or answer_index >= len(options) or answer_index < 0:
                answer_index = 0
            explanation = clean_text(str(q.get('explanation', '')))[:240]
            q_ok, _ = is_quality_chunk(question + ' ' + ' '.join(options))
            if not q_ok:
                continue
            clean_quiz.append(
                {
                    'id': i,
                    'question': question,
                    'options': options,
                    'answer_index': answer_index,
                    'explanation': explanation or 'Derived from source content.',
                }
            )

    if not clean_quiz:
        clean_quiz = fallback['quiz']

    return {
        'summary': summary,
        'key_points': clean_points[:6],
        'glossary': glossary,
        'quiz': clean_quiz[:6],
    }


def _resolve_ollama_settings(user: User | None) -> tuple[bool, str, str, int]:
    enabled = settings.local_llm_enabled
    base_url = settings.local_llm_url or settings.ollama_base_url
    model = settings.local_llm_model or settings.ollama_model
    timeout = settings.ollama_timeout_read_seconds or settings.ollama_timeout_seconds
    if user is not None:
        if user.use_ollama is not None:
            enabled = user.use_ollama
        if user.ollama_base_url:
            base_url = user.ollama_base_url
        if user.ollama_model:
            model = user.ollama_model
        if user.ollama_timeout_seconds:
            timeout = user.ollama_timeout_seconds
    return enabled, base_url, model, timeout


async def generate_education(chunks: list[str], user: User | None = None) -> dict:
    fallback = _local_summary(chunks)
    use_ollama, base_url, model, timeout = _resolve_ollama_settings(user)
    if not use_ollama:
        return fallback

    # Condense source context before prompt build to avoid timeout-inducing huge prompts.
    condensed_chunks = []
    for chunk in chunks[:24]:
        cleaned = clean_text(chunk)
        if not cleaned:
            continue
        condensed_chunks.append(cleaned[:500])
        if len('\n'.join(condensed_chunks)) >= settings.local_llm_prompt_budget_chars // 2:
            break
    context = '\n'.join(condensed_chunks)
    prompt = (
        'You are a study coach. Return JSON only with keys summary, key_points, glossary, quiz. '
        'quiz must be a list of MCQs with fields question, options (4), answer_index, explanation. '
        'Use only source content and avoid binary/pdf artifacts.\n\n'
        f'SOURCE:\n{context}'
    )

    try:
        response_text = await ollama_generate(
            prompt,
            base_url=base_url,
            model=model,
            timeout_seconds=timeout,
        )
    except Exception as exc:
        raise ValueError(
            f'Local LLM generation failed ({type(exc).__name__}): {exc}. '
            'Try lowering prompt size, increasing OLLAMA_TIMEOUT_READ_SECONDS, or verifying model availability.'
        ) from exc
    parsed = _extract_json(response_text)
    if not parsed:
        return fallback
    return _sanitize_payload(parsed, fallback)
