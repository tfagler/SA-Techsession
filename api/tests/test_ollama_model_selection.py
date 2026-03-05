import pytest
from app.services.ollama_client import _pick_model


def test_pick_model_uses_requested_when_available():
    assert _pick_model('qwen3.5:9b', {'qwen3.5:9b', 'llama3:latest'}) == 'qwen3.5:9b'


def test_pick_model_errors_when_requested_missing():
    with pytest.raises(ValueError) as exc:
        _pick_model('qwen3.5:9b', {'llama3:latest'})
    assert "qwen3.5:9b" in str(exc.value)
    assert 'Set LOCAL_LLM_MODEL' in str(exc.value)
