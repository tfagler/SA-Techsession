from app.services.ollama_client import build_ollama_endpoints, normalize_ollama_base_url


def test_normalize_ollama_base_url_strips_trailing_api():
    assert normalize_ollama_base_url('http://192.168.252.6:11434/api') == 'http://192.168.252.6:11434'
    assert normalize_ollama_base_url('http://192.168.252.6:11434/api/') == 'http://192.168.252.6:11434'


def test_normalize_ollama_base_url_preserves_root():
    base = normalize_ollama_base_url('http://192.168.252.6:11434')
    assert base == 'http://192.168.252.6:11434'
    generate_url, chat_url = build_ollama_endpoints(base)
    assert generate_url == 'http://192.168.252.6:11434/api/generate'
    assert chat_url == 'http://192.168.252.6:11434/api/chat'
    assert '/api/api/' not in generate_url
