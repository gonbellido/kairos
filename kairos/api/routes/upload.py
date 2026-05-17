import logging
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, Request, UploadFile, File, Form

from kairos.core.memory import RawMemory
from kairos.storage.minio_client import get_storage

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/upload/audio")
async def upload_audio(
    req: Request, file: UploadFile = File(...),
    client_id: str = Form(""), profile_id: str = Form("coaching"),
):
    runtime = req.app.state.runtime
    contents = await file.read()
    filename = file.filename or "audio.wav"
    ct = file.content_type or "audio/wav"

    # Obtener coach_id del token
    token = req.cookies.get("kairos_token")
    coach = await req.app.state.coach_db.get_session(token) if token else None
    coach_id = coach["id"] if coach else "anonymous"

    # Fase F: Guardar en MinIO con aislamiento
    try:
        storage = get_storage()
        meta = storage.upload(
            coach_id=coach_id,
            client_id=client_id,
            filename=filename,
            data=contents,
            content_type=ct,
        )
        logger.info("Audio stored in MinIO: %s", meta["object_path"])
    except Exception as e:
        logger.warning("MinIO upload failed (non-blocking): %s", e)
        meta = {"object_path": f"local://{filename}", "sha256": "fallback"}

    # Temp file for pipeline processing
    upload_dir = Path("/tmp/kairos_uploads")
    upload_dir.mkdir(exist_ok=True)
    file_path = upload_dir / f"{uuid4().hex}{Path(filename).suffix}"
    file_path.write_bytes(contents)

    # Process through pipeline
    context = {"client_id": client_id, "_audio_path": str(file_path)}
    result = await runtime.run(
        session_id=uuid4().hex,
        profile_id=profile_id,
        message="[transcripción de audio]",
        user_id=client_id or "default",
        context=context,
    )

    # Store raw memory reference
    raw = RawMemory(
        profile_id=profile_id,
        client_id=client_id,
        coach_id=coach_id,
        content=f"[Audio] {filename} ({len(contents)} bytes) · MinIO: {meta['object_path']}",
        source_type="audio_upload",
        metadata={
            "original_name": filename,
            "size": len(contents),
            "minio_path": meta.get("object_path", ""),
            "sha256": meta.get("sha256", ""),
        },
    )
    await runtime.raw_store.store(raw)

    return {
        "status": "ok",
        "filename": filename,
        "size": len(contents),
        "client_id": client_id,
        "minio_path": meta.get("object_path", ""),
    }


@router.post("/upload/document")
async def upload_document(
    req: Request, file: UploadFile = File(...),
    client_id: str = Form(""), profile_id: str = Form("coaching"),
):
    runtime = req.app.state.runtime
    contents = await file.read()
    filename = file.filename or "documento"
    ct = file.content_type or "application/octet-stream"

    token = req.cookies.get("kairos_token")
    coach = await req.app.state.coach_db.get_session(token) if token else None
    coach_id = coach["id"] if coach else "anonymous"

    # Fase F: Guardar en MinIO con aislamiento
    try:
        storage = get_storage()
        meta = storage.upload(
            coach_id=coach_id,
            client_id=client_id,
            filename=filename,
            data=contents,
            content_type=ct,
        )
        logger.info("Document stored in MinIO: %s", meta["object_path"])
    except Exception as e:
        logger.warning("MinIO upload failed (non-blocking): %s", e)
        meta = {"object_path": f"local://{filename}", "sha256": "fallback"}

    # Extraer texto para embedding
    try:
        from kairos.engine.text_extractor import extract_text
        texto = extract_text(filename, contents)
    except Exception:
        try:
            texto = contents.decode("utf-8", errors="replace")[:5000]
        except Exception:
            texto = filename

    raw = RawMemory(
        profile_id=profile_id,
        client_id=client_id,
        coach_id=coach_id,
        content=texto,
        source_type=Path(filename).suffix.lower().replace(".", ""),
        metadata={
            "original_name": filename,
            "size": len(contents),
            "minio_path": meta.get("object_path", ""),
            "sha256": meta.get("sha256", ""),
        },
    )
    await runtime.raw_store.store(raw)

    return {
        "status": "ok",
        "filename": filename,
        "size": len(contents),
        "client_id": client_id,
        "minio_path": meta.get("object_path", ""),
    }
