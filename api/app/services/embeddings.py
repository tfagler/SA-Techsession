import hashlib
import math
from app.config import get_settings


settings = get_settings()


def embed_text(text: str) -> list[float]:
    dim = settings.embed_dim
    vec = [0.0] * dim
    words = text.lower().split()
    if not words:
        return vec
    for w in words:
        h = int(hashlib.sha256(w.encode('utf-8')).hexdigest(), 16)
        idx = h % dim
        vec[idx] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))
