"""Document ingestion, the processing pipeline, and deletion.

Consistency strategy (PostgreSQL <-> Qdrant are not atomic):
  * chunk rows are the source of truth; vectors are derived and keyed by chunk id (deterministic point ids).
  * (re)processing deletes the document's existing vectors before upserting, so retries never duplicate entries.
  * deletion removes vectors first, then the file, then DB rows; on partial failure the document is kept with
    deletion_state='delete_failed' so the problem is visible and the delete can be retried.
"""
import hashlib
import logging
import time
import uuid
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError, ServiceUnavailable
from app.models import (
    ClassificationPrediction,
    DocStatus,
    Document,
    DocumentChunk,
    ProcessingEvent,
    ProcessingJob,
    VerifiedClassification,
    _now,
)
from app.services import classification_service, entity_service, extraction_service
from app.services.embedding_service import get_embedder
from app.services.vector_store import get_vector_store

log = logging.getLogger("infomind.documents")


def storage_path(storage_id: str) -> Path:
    base = get_settings().storage_dir.resolve()
    p = (base / storage_id).resolve()
    if base not in p.parents:  # defence in depth: storage_id is server-generated hex, but verify anyway
        raise AppError("Invalid storage path", status_code=500, code="storage_error")
    return p


def add_event(db: Session, doc: Document, stage: str, message: str = "") -> None:
    db.add(ProcessingEvent(document_id=doc.id, stage=stage, message=message[:500]))


def set_status(db: Session, doc: Document, status: DocStatus, message: str = "") -> None:
    doc.status = status.value
    add_event(db, doc, status.value, message)
    db.commit()


def enqueue(db: Session, doc: Document) -> ProcessingJob:
    existing = db.scalar(select(ProcessingJob).where(
        ProcessingJob.document_id == doc.id, ProcessingJob.status.in_(("pending", "running"))))
    if existing:
        return existing
    job = ProcessingJob(document_id=doc.id)
    db.add(job)
    set_status(db, doc, DocStatus.queued, "Queued for processing")
    return job


def ingest_upload(db: Session, owner_id: str, filename: str, declared_mime: str | None,
                  data: bytes, *, is_demo: bool = False) -> tuple[Document, bool]:
    """Validate, deduplicate (per owner, by SHA-256), store and enqueue. Returns (document, is_duplicate)."""
    s = get_settings()
    filename = extraction_service.safe_filename(filename)
    ext = extraction_service.validate_upload(filename, declared_mime, data, s.max_upload_bytes)
    digest = hashlib.sha256(data).hexdigest()
    existing = db.scalar(select(Document).where(Document.owner_id == owner_id, Document.sha256 == digest))
    if existing:
        return existing, True
    storage_id = uuid.uuid4().hex
    s.storage_dir.mkdir(parents=True, exist_ok=True)
    path = storage_path(storage_id)
    path.write_bytes(data)
    doc = Document(owner_id=owner_id, filename=filename, storage_id=storage_id, extension=ext,
                   mime_type=extraction_service.CANONICAL_MIME[ext], size_bytes=len(data), sha256=digest,
                   status=DocStatus.uploaded.value, is_demo=is_demo)
    db.add(doc)
    try:
        db.commit()
    except Exception:
        db.rollback()
        path.unlink(missing_ok=True)
        raise
    add_event(db, doc, DocStatus.uploaded.value, "File accepted")
    db.commit()
    enqueue(db, doc)
    return doc, False


def process_document(db: Session, document_id: str) -> tuple[bool, bool]:
    """Run the pipeline. Returns (success, retryable). Idempotent: previous chunks/vectors are replaced."""
    doc = db.get(Document, document_id)
    if doc is None:
        return False, False
    s = get_settings()
    doc.error_message = None
    retryable, embed_error = False, None
    try:
        set_status(db, doc, DocStatus.extracting)
        pages = extraction_service.extract_pages(storage_path(doc.storage_id), doc.extension)
        if not pages:
            raise extraction_service.ValidationError("No extractable text was found (scanned documents need OCR).")
        doc.extracted_text = "\n\n".join(p.text for p in pages)
        doc.page_count = len([p for p in pages if p.number]) or None

        set_status(db, doc, DocStatus.chunking)
        chunks = extraction_service.chunk_pages(pages, s.chunk_size_chars, s.chunk_overlap_chars)
        db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == doc.id))
        db.expire(doc, ["chunks"])
        rows =[DocumentChunk(document_id=doc.id, chunk_index=c.index, page=c.page, text=c.text) for c in chunks]
        db.add_all(rows)
        doc.chunk_count = len(rows)
        db.commit()

        set_status(db, doc, DocStatus.embedding)
        try:
            store = get_vector_store()
            store.delete_document(doc.id)
            vectors = get_embedder().embed([r.text for r in rows])
            store.upsert([(r.id, v, {"document_id": doc.id, "chunk_id": r.id, "owner_id": doc.owner_id,
                                      "page": r.page, "chunk_index": r.chunk_index, "extension": doc.extension})
                          for r, v in zip(rows, vectors, strict=True)])
            set_status(db, doc, DocStatus.indexed, f"{len(rows)} chunks indexed")
        except ServiceUnavailable as exc:
            embed_error, retryable = exc.message, True
            add_event(db, doc, "embedding", f"Embedding/indexing unavailable: {exc.message}")
            db.commit()

        set_status(db, doc, DocStatus.classifying)
        pred = classification_service.classify_document(db, doc)
        add_event(db, doc, "classifying", f"Predicted: {pred.category}" if pred else "No trained model; skipped")
        entity_service.index_document_entities(db, doc.id)

        if embed_error:
            doc.error_message = (f"Text was extracted and keyword search works, but semantic indexing failed: "
                                 f"{embed_error} Reprocess once the service is available.")
            set_status(db, doc, DocStatus.failed, "Semantic indexing incomplete")
            return False, retryable
        set_status(db, doc, DocStatus.completed)
        return True, False
    except (extraction_service.ValidationError, FileNotFoundError, ValueError) as exc:
        return _fail(db, doc, f"Could not read the document: {exc}" if not isinstance(exc, extraction_service.ValidationError)
                     else str(exc))
    except Exception:  # noqa: BLE001 - logged in full; users get a generic message without paths or internals
        log.exception("Processing failed for document %s", document_id)
        return _fail(db, doc, "Processing failed unexpectedly. See server logs.")


def _fail(db: Session, doc: Document, message: str) -> tuple[bool, bool]:
    db.rollback()
    doc = db.get(Document, doc.id)
    doc.error_message = message[:1000]
    set_status(db, doc, DocStatus.failed, message[:300])
    return False, False


def claim_next_job(db: Session) -> ProcessingJob | None:
    from sqlalchemy import update

    job = db.scalar(select(ProcessingJob).where(ProcessingJob.status == "pending").order_by(ProcessingJob.created_at))
    if job is None:
        return None
    res = db.execute(update(ProcessingJob).where(ProcessingJob.id == job.id, ProcessingJob.status == "pending")
                     .values(status="running", attempts=ProcessingJob.attempts + 1, updated_at=_now()))
    db.commit()
    if res.rowcount != 1:  # another worker won the race
        return None
    db.refresh(job)
    return job


def run_job(db: Session, job: ProcessingJob) -> None:
    started = time.monotonic()
    ok, retryable = process_document(db, job.document_id)
    job = db.get(ProcessingJob, job.id)
    job.duration_ms = int((time.monotonic() - started) * 1000)
    if ok:
        job.status = "done"
    elif retryable and job.attempts < get_settings().max_job_attempts:
        job.status = "pending"
    else:
        job.status = "failed"
        doc = db.get(Document, job.document_id)
        job.error_message = doc.error_message if doc else "document missing"
    db.commit()


def run_pending_jobs(db: Session, limit: int = 100) -> int:
    n = 0
    while n < limit and (job := claim_next_job(db)) is not None:
        run_job(db, job)
        n += 1
    return n


def delete_document(db: Session, doc: Document) -> None:
    try:
        get_vector_store().delete_document(doc.id)
        storage_path(doc.storage_id).unlink(missing_ok=True)
    except Exception as exc:
        doc.deletion_state = "delete_failed"
        add_event(db, doc, "delete", "Deletion incomplete; retry the delete")
        db.commit()
        raise ServiceUnavailable("Deletion could not be completed; the document is flagged for retry.") from exc
    for model in (ClassificationPrediction, VerifiedClassification):
        for row in db.scalars(select(model).where(model.document_id == doc.id)):
            db.delete(row)
    db.delete(doc)  # chunks, jobs, events, entities, reviews cascade via FK ondelete / relationship cascade
    db.commit()
