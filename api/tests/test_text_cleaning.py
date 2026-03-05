from app.services.text_cleaning import clean_text, is_quality_chunk


def test_rejects_pdf_structure_tokens():
    text = '%PDF-1.7 xref obj endobj stream endstream this is not real lesson content'
    ok, reason = is_quality_chunk(text)
    assert not ok
    assert reason == 'pdf_structure_tokens'


def test_accepts_human_readable_chunk():
    text = clean_text('Kubernetes pods are the smallest deployable units in a cluster and run one or more containers.')
    ok, reason = is_quality_chunk(text)
    assert ok
    assert reason is None
