"""Advanced chunking for RAG — semantic boundaries, metadata preservation, cross-document reranking."""

import re
from typing import Any


def detect_section_headers(text: str) -> list[tuple[int, int, str]]:
    """Find markdown-style section headers and return (start, end, title)."""
    headers = []
    for m in re.finditer(r"^(#{1,6}\s+.+)$", text, re.MULTILINE):
        headers.append((m.start(), m.end(), m.group(1).strip()))
    return headers


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    """Divide text into overlapping chunks, preferring semantic boundaries."""
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end]

        if end < len(text):
            for sep in ["\n\n", "\n", ". ", "? ", "! ", " "]:
                pos = chunk.rfind(sep, max(0, len(chunk) - 150))
                if pos > 0:
                    end = start + pos + len(sep)
                    chunk = text[start:end]
                    break

        chunks.append(chunk.strip())
        start = end - overlap if end < len(text) else end

    return [c for c in chunks if len(c) > 50]


def chunk_document(content: str, filename: str, chunk_size: int = 800, overlap: int = 100) -> list[dict[str, Any]]:
    """Chunk document text with semantic awareness and metadata."""
    headers = detect_section_headers(content)
    current_section = ""

    chunks = chunk_text(content, chunk_size, overlap)
    result = []
    for i, chunk in enumerate(chunks):
        section = current_section
        for h_start, h_end, h_title in headers:
            pos_in_doc = content.find(chunk[:50])
            if pos_in_doc >= 0 and h_start < pos_in_doc:
                section = h_title
                current_section = h_title

        result.append({
            "index": i,
            "total": len(chunks),
            "text": chunk,
            "filename": filename,
            "section": section,
        })
    return result


def rerank_by_document(chunks: list[dict], top_k: int = 5) -> list[dict]:
    """Cross-document reranking: ensure diverse sources in top results."""
    seen_sources: set[str] = set()
    ranked = []
    for c in sorted(chunks, key=lambda x: x.get("_score", 0), reverse=True):
        src = c.get("filename", "") or c.get("document_id", "")
        if src not in seen_sources or len(seen_sources) >= top_k:
            ranked.append(c)
            if src:
                seen_sources.add(src)
        if len(ranked) >= top_k:
            break
    return ranked
