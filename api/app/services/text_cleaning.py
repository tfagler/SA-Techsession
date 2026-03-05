import re
import string


PDF_STRUCTURE_TOKENS = ('%pdf-', 'xref', 'obj', 'endobj', 'stream', 'endstream')


def normalize_whitespace(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()


def non_printable_ratio(text: str) -> float:
    if not text:
        return 1.0
    bad = 0
    for ch in text:
        if ch in '\n\r\t':
            continue
        if ch not in string.printable:
            bad += 1
    return bad / max(1, len(text))


def has_pdf_structure_tokens(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in PDF_STRUCTURE_TOKENS)


def clean_text(text: str) -> str:
    return normalize_whitespace(text.replace('\x00', ''))


def is_quality_chunk(text: str) -> tuple[bool, str | None]:
    cleaned = clean_text(text)
    if len(cleaned) < 40:
        return False, 'too_short_chars'
    if len(cleaned.split()) < 8:
        return False, 'too_short_words'
    if has_pdf_structure_tokens(cleaned):
        return False, 'pdf_structure_tokens'
    if non_printable_ratio(cleaned) > 0.02:
        return False, 'non_printable_ratio'
    return True, None
