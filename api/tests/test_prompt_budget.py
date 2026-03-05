import pytest
from app.services import ollama_client


def test_prompt_budget_truncates_when_over_budget(monkeypatch):
    monkeypatch.setattr(ollama_client.settings, 'local_llm_prompt_budget_tokens', 200)
    monkeypatch.setattr(ollama_client.settings, 'local_llm_prompt_budget_chars', 800)
    monkeypatch.setattr(ollama_client.settings, 'local_llm_prompt_policy', 'truncate')

    prompt = 'word ' * 2000
    out = ollama_client.enforce_prompt_budget(prompt)
    assert len(out) <= 800
    assert ollama_client.estimate_tokens(out) <= 200


def test_prompt_budget_rejects_when_policy_reject(monkeypatch):
    monkeypatch.setattr(ollama_client.settings, 'local_llm_prompt_budget_tokens', 100)
    monkeypatch.setattr(ollama_client.settings, 'local_llm_prompt_budget_chars', 600)
    monkeypatch.setattr(ollama_client.settings, 'local_llm_prompt_policy', 'reject')

    prompt = 'word ' * 2000
    with pytest.raises(ValueError) as exc:
        ollama_client.enforce_prompt_budget(prompt)
    assert 'Prompt exceeds budget' in str(exc.value)
