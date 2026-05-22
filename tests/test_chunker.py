"""Tests for enhanced chunker."""

from kairos.engine.chunker import chunk_text, chunk_document, detect_section_headers, rerank_by_document


def test_chunk_short_text():
    assert chunk_text("Hello world") == ["Hello world"]


def test_chunk_long_text():
    text = "Word. " * 300
    chunks = chunk_text(text)
    assert len(chunks) > 1
    assert all(len(c) > 50 for c in chunks)


def test_detect_headers():
    text = "# Title\n\nSome text\n## Subsection\n\nMore text"
    headers = detect_section_headers(text)
    assert len(headers) == 2
    assert headers[0][2] == "# Title"
    assert headers[1][2] == "## Subsection"


def test_chunk_document():
    doc = chunk_document("# Intro\n\nHello world.\n\n## Details\n\nMore content here.\n\nEven more.", "test.md")
    assert len(doc) > 0
    assert doc[0]["filename"] == "test.md"


def test_rerank_by_document():
    chunks = [
        {"filename": "a.pdf", "_score": 0.9, "text": "aaa"},
        {"filename": "a.pdf", "_score": 0.8, "text": "bbb"},
        {"filename": "b.pdf", "_score": 0.7, "text": "ccc"},
    ]
    ranked = rerank_by_document(chunks, top_k=2)
    assert len(ranked) == 2
    assert ranked[0]["filename"] == "a.pdf"
    assert ranked[1]["filename"] == "b.pdf"
