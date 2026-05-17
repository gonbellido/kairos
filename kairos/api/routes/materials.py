import logging
from uuid import uuid4

from fastapi import APIRouter, Request, UploadFile, File, Form

from kairos.core.memory import RawMemory
from kairos.engine.chunker import chunk_document
from kairos.storage.minio_client import get_storage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/materials", tags=["materials"])

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100


@router.get("/")
async def list_materials(req: Request):
    """Coach materials: grouped by document (chunks aggregated)."""
    token = req.cookies.get("kairos_token")
    coach = await req.app.state.coach_db.get_session(token) if token else None
    coach_id = coach["id"] if coach else ""

    rs = req.app.state.runtime.raw_store
    items = rs.list_by_filter(profile_id="coaching", client_id="", coach_id=coach_id, limit=500)

    # Agrupar chunks por document_id
    docs: dict[str, dict] = {}
    for pay in items:
        content = (pay.get("content", "") or "")
        doc_id = pay.get("metadata", {}).get("document_id", pay.get("_point_id", ""))
        chunk_idx = pay.get("metadata", {}).get("chunk_index", 0)
        chunk_total = pay.get("metadata", {}).get("chunk_total", 1)
        name = pay.get("metadata", {}).get("original_name", "documento")

        if doc_id not in docs:
            is_binary = (
                content.startswith("[Archivo binario:") or
                content.startswith("[PDF sin extraer") or
                content.startswith("[RTF sin extraer") or
                content.startswith("[DOCX sin extraer")
            )
            is_rtf = content.startswith("{\\rtf")
            docs[doc_id] = {
                "id": doc_id,
                "name": name,
                "source_type": pay.get("source_type", ""),
                "size": pay.get("metadata", {}).get("size", 0),
                "created_at": pay.get("created_at", ""),
                "chunks": chunk_total,
                "embedded": len(content.strip()) > 1 and not is_binary,
                "status": "rtf_raw" if is_rtf else ("embedded" if len(content.strip()) > 1 else "sin_texto"),
                "warning": "RTF de macOS — guardar como texto plano" if is_rtf else None,
                "content_preview": content[:300] if not is_rtf else "[RTF]",
            }

    materials = sorted(docs.values(), key=lambda d: d.get("created_at", ""), reverse=True)
    return {"materials": materials}


@router.post("/upload")
async def upload_material(req: Request, file: UploadFile = File(...), tags: str = Form("")):
    token = req.cookies.get("kairos_token")
    coach = await req.app.state.coach_db.get_session(token) if token else None
    coach_id = coach["id"] if coach else "anonymous"

    runtime = req.app.state.runtime
    contents = await file.read()
    ct = file.content_type or ""
    source_type = "audio_upload" if ct.startswith("audio/") else "document"
    filename = file.filename or "documento"

    # Extraer texto completo (sin límite)
    try:
        from kairos.engine.text_extractor import extract_text
        texto = extract_text(filename, contents)
    except Exception:
        try:
            texto = contents.decode("utf-8", errors="replace")
        except Exception:
            texto = f"[Archivo binario: {filename}, {len(contents)} bytes]"

    # Fase F: Guardar original en MinIO
    try:
        storage = get_storage()
        minio_meta = storage.upload(
            coach_id=coach_id,
            client_id="",  # materiales del coach (globales)
            filename=filename,
            data=contents,
            content_type=ct,
        )
        logger.info("Material stored in MinIO: %s", minio_meta["object_path"])
    except Exception as e:
        logger.warning("MinIO material upload failed (non-blocking): %s", e)
        minio_meta = {"object_path": "", "sha256": ""}

    # Chunkear el documento completo
    doc_id = uuid4().hex
    chunks = chunk_document(texto, filename, CHUNK_SIZE, CHUNK_OVERLAP)

    stored_ids = []
    for ch in chunks:
        raw = RawMemory(
            profile_id="coaching",
            client_id="",
            coach_id=coach_id,
            content=ch["text"],
            source_type=source_type,
            metadata={
                "original_name": filename,
                "document_id": doc_id,
                "chunk_index": ch["index"],
                "chunk_total": ch["total"],
                "size": len(contents),
                "tags": tags,
                "mime": ct or "application/octet-stream",
                "minio_path": minio_meta.get("object_path", ""),
                "sha256": minio_meta.get("sha256", ""),
            },
        )
        sid = await runtime.raw_store.store(raw)
        stored_ids.append(sid)

    logger.info("Material uploaded: %s (%d bytes, %d chunks, doc_id=%s, coach=%s)",
                filename, len(contents), len(chunks), doc_id, coach_id)
    return {
        "status": "ok",
        "filename": filename,
        "size": len(contents),
        "id": doc_id,
        "chunks": len(chunks),
    }


@router.delete("/{material_id}")
async def delete_material(req: Request, material_id: str):
    """Elimina un material y todos sus chunks por document_id."""
    runtime = req.app.state.runtime

    # Encontrar todos los chunks con este document_id
    token = req.cookies.get("kairos_token")
    coach = await req.app.state.coach_db.get_session(token) if token else None
    coach_id = coach["id"] if coach else ""

    items = runtime.raw_store.list_by_filter(
        profile_id="coaching", client_id="", coach_id=coach_id, limit=500
    )
    deleted = 0
    for pay in items:
        doc_id = pay.get("metadata", {}).get("document_id", "")
        pid = pay.get("_point_id", "")
        if doc_id == material_id or pid == material_id:
            if runtime.raw_store.delete_by_point_id(pid):
                deleted += 1

    logger.info("Material deleted: doc_id=%s, %d chunks removed", material_id, deleted)
    return {"status": "deleted" if deleted > 0 else "not_found", "chunks_removed": deleted}
