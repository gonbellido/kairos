"""Chunking de documentos para embedding sin pérdida de contexto."""

import re
from typing import Any


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    """Divide un texto en chunks solapados para embedding.
    
    Prioriza cortes en saltos de párrafo o fin de frase.
    chunk_size: caracteres por chunk (~500 tokens)
    overlap: solapamiento entre chunks para mantener contexto
    """
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end]

        # Buscar un buen punto de corte cerca del final (párrafo, punto, espacio)
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
    """Chunk document text into embeddable pieces with metadata."""
    chunks = chunk_text(content, chunk_size, overlap)
    result = []
    for i, chunk in enumerate(chunks):
        result.append({
            "index": i,
            "total": len(chunks),
            "text": chunk,
            "filename": filename,
        })
    return result
