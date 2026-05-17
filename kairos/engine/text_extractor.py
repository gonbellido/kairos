"""Extract clean text from uploaded files (PDF, DOCX, RTF, TXT, MD, etc.)"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from pypdf import PdfReader as _PdfReader
    _PYPDF_AVAILABLE = True
except ImportError:
    _PYPDF_AVAILABLE = False
    logger.warning("pypdf no instalado — PDFs no se extraerán correctamente. pip install pypdf")

try:
    from striprtf.striprtf import rtf_to_text as _rtf_to_text
    _STRIPRTF_AVAILABLE = True
except ImportError:
    _STRIPRTF_AVAILABLE = False
    logger.warning("striprtf no instalado — RTFs no se extraerán. pip install striprtf")

try:
    from docx import Document as _DocxDocument
    _DOCX_AVAILABLE = True
except ImportError:
    _DOCX_AVAILABLE = False
    logger.warning("python-docx no instalado — DOCX no se extraerán. pip install python-docx")


def extract_text(filename: str, content: bytes) -> str:
    ext = Path(filename).suffix.lower() if filename else ".txt"

    # Detectar RTF por contenido (macOS guarda .md como RTF)
    if content[:5] == b"{\\rtf":
        return _extract_rtf(content)

    try:
        if ext == ".pdf":
            return _extract_pdf(content)
        elif ext == ".rtf":
            return _extract_rtf(content)
        elif ext == ".docx":
            return _extract_docx(content)
        elif ext in (".md", ".csv", ".json", ".txt", ".log", ".yaml", ".yml"):
            return content.decode("utf-8", errors="replace")[:10000]
        else:
            return content.decode("utf-8", errors="replace")[:5000]
    except Exception as e:
        logger.warning("Extracción de texto falló para %s: %s", filename, e)
        return content.decode("utf-8", errors="replace")[:2000]


def _extract_pdf(content: bytes) -> str:
    if not _PYPDF_AVAILABLE:
        logger.error(
            "pypdf no instalado. Instala con: pip install pypdf\n"
            "El PDF se indexará sin texto — el RAG no funcionará sobre este documento."
        )
        return "[PDF sin extraer: instala pypdf para habilitar extracción]"
    import io
    reader = _PdfReader(io.BytesIO(content))
    text = []
    for page in reader.pages:
        t = page.extract_text()
        if t:
            text.append(t)
    return "\n".join(text)[:10000]


def _extract_rtf(content: bytes) -> str:
    if not _STRIPRTF_AVAILABLE:
        logger.error(
            "striprtf no instalado. Instala con: pip install striprtf\n"
            "El RTF se indexará sin texto."
        )
        return "[RTF sin extraer: instala striprtf para habilitar extracción]"
    raw = content.decode("utf-8", errors="replace")
    return _rtf_to_text(raw)[:10000]


def _extract_docx(content: bytes) -> str:
    if not _DOCX_AVAILABLE:
        logger.error(
            "python-docx no instalado. Instala con: pip install python-docx\n"
            "El DOCX se indexará sin texto."
        )
        return "[DOCX sin extraer: instala python-docx para habilitar extracción]"
    import io
    doc = _DocxDocument(io.BytesIO(content))
    text = [p.text for p in doc.paragraphs if p.text]
    return "\n".join(text)[:10000]
