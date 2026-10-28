from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_authorized_document, get_current_user, is_admin, require_roles
from app.core.config import get_settings
from app.core.errors import AppError, NotFound
from app.core.ratelimit import rate_limit
from app.db.session import SessionLocal, get_db
from app.models import (
    ClassificationPrediction,
    Document,
    ExtractedEntity,
    ProcessingEvent,
    Role,
    User,
    VerifiedClassification,
)
from app.schemas import (
    DocumentDetail,
    DocumentList,
    DocumentOut,
    EntityOut,
    EventOut,
    PredictionOut,
    UploadBatch,
    UploadError,
    UploadResult,
)
from app.services import audit_service, classification_service, document_service, extraction_service

router = APIRouter(prefix="/documents", tags=["documents"])


def _to_out(db: Session, doc: Document) -> DocumentOut:
    out = DocumentOut.model_validate(doc)
    pred = classification_service.current_prediction(db, doc.id)
    ver = db.get(VerifiedClassification, doc.id)
    out.prediction = PredictionOut.model_validate(pred) if pred else None
    out.verified_category = ver.category if ver else None
    out.category = ver.category if ver else (pred.category if pred else None)
    return out


def _kick_worker(background: BackgroundTasks) -> None:
    if get_settings().run_worker_in_api:
        background.add_task(_drain_jobs)


def _drain_jobs() -> None:
    db = SessionLocal()
    try:
        document_service.run_pending_jobs(db)
    finally:
        db.close()


@router.post("", response_model=UploadBatch, status_code=201, dependencies=[rate_limit("upload", 20)])
async def upload(request: Request, background: BackgroundTasks, files: list[UploadFile] = File(...),
                 user: User = Depends(require_roles(Role.analyst)), db: Session = Depends(get_db)):
    if len(files) > 20:
        raise AppError("At most 20 files can be uploaded at once.", code="too_many_files")
    limit = get_settings().max_upload_bytes
    results, errors = [], []
    for f in files:
        name = extraction_service.safe_filename(f.filename)
        data = await f.read(limit + 1)  # bounded read: never buffer more than limit+1 bytes
        try:
            doc, dup = document_service.ingest_upload(db, user.id, name, f.content_type, data)
        except extraction_service.ValidationError as exc:
            errors.append(UploadError(filename=name, error=str(exc)))
            audit_service.record(db, action="document.upload", outcome="failure", actor_id=user.id,
                                 request=request, detail=f"{name}: {exc}")
            continue
        if not dup:
            audit_service.record(db, action="document.upload", actor_id=user.id, target_type="document",
                                 target_id=doc.id, request=request)
        results.append(UploadResult(document=_to_out(db, doc), duplicate=dup))
    _kick_worker(background)
    return UploadBatch(results=results, errors=errors)


@router.get("", response_model=DocumentList)
def list_documents(status: str | None = None, category: str | None = None, file_type: str | None = None,
                   q: str | None = Query(default=None, max_length=200),
                   sort: str = Query(default="-created_at", pattern="^-?(created_at|filename|size_bytes)$"),
                   page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = select(Document)
    if not is_admin(user):
        stmt = stmt.where(Document.owner_id == user.id)
    if status:
        stmt = stmt.where(Document.status == status)
    if file_type:
        stmt = stmt.where(Document.extension == file_type.lower().lstrip("."))
    if q:
        stmt = stmt.where(Document.filename.ilike(f"%{q}%"))
    if category:
        pred_ids = select(ClassificationPrediction.document_id).where(
            ClassificationPrediction.category == category, ClassificationPrediction.is_current.is_(True),
            ~ClassificationPrediction.document_id.in_(select(VerifiedClassification.document_id)))
        ver_ids = select(VerifiedClassification.document_id).where(VerifiedClassification.category == category)
        stmt = stmt.where(Document.id.in_(pred_ids) | Document.id.in_(ver_ids))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    col = getattr(Document, sort.lstrip("-"))
    stmt = stmt.order_by(col.desc() if sort.startswith("-") else col.asc()).offset((page - 1) * page_size).limit(page_size)
    items = [_to_out(db, d) for d in db.scalars(stmt)]
    return DocumentList(items=items, total=total, page=page, page_size=page_size)


@router.get("/{document_id}", response_model=DocumentDetail)
def get_document(document_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = get_authorized_document(db, user, document_id)
    base = _to_out(db, doc)
    events = db.scalars(select(ProcessingEvent).where(ProcessingEvent.document_id == doc.id)
                        .order_by(ProcessingEvent.created_at))
    entities = db.scalars(select(ExtractedEntity).where(ExtractedEntity.document_id == doc.id,
                                                       ExtractedEntity.removed.is_(False)).order_by(ExtractedEntity.label))
    indexed = doc.status in ("indexed", "completed")
    return DocumentDetail(**base.model_dump(), text_preview=(doc.extracted_text or "")[:3000],
                          events=[EventOut.model_validate(e) for e in events],
                          entities=[EntityOut.model_validate(e) for e in entities], indexed=indexed)


@router.get("/{document_id}/content")
def get_content(document_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = get_authorized_document(db, user, document_id)
    return {"document_id": doc.id, "filename": doc.filename, "text": (doc.extracted_text or "")[:500_000],
            "truncated": len(doc.extracted_text or "") > 500_000}


@router.get("/{document_id}/download")
def download(document_id: str, request: Request, user: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    doc = get_authorized_document(db, user, document_id)
    path = document_service.storage_path(doc.storage_id)
    if not path.exists():
        raise NotFound("The stored file is missing.")
    audit_service.record(db, action="document.download", actor_id=user.id, target_type="document",
                         target_id=doc.id, request=request)
    return FileResponse(path, media_type=doc.mime_type, filename=doc.filename,
                        headers={"X-Content-Type-Options": "nosniff"})


@router.post("/{document_id}/reprocess", response_model=DocumentOut, status_code=202)
def reprocess(document_id: str, request: Request, background: BackgroundTasks,
              user: User = Depends(require_roles(Role.analyst)), db: Session = Depends(get_db)):
    doc = get_authorized_document(db, user, document_id)
    if not document_service.storage_path(doc.storage_id).exists():  # refuse before changing the document's state
        raise AppError(document_service.FILE_GONE, status_code=409, code="file_missing")
    document_service.enqueue(db, doc)
    audit_service.record(db, action="document.reprocess", actor_id=user.id, target_type="document",
                         target_id=doc.id, request=request)
    _kick_worker(background)
    return _to_out(db, doc)


@router.post("/{document_id}/reclassify", response_model=DocumentOut)
def reclassify(document_id: str, request: Request, user: User = Depends(require_roles(Role.analyst)),
               db: Session = Depends(get_db)):
    doc = get_authorized_document(db, user, document_id)
    if classification_service.active_model_version(db) is None:
        raise AppError("No trained classification model is available.", status_code=409, code="no_model")
    if not doc.extracted_text:
        raise AppError("The document has no extracted text yet.", status_code=409, code="not_processed")
    classification_service.classify_document(db, doc)
    audit_service.record(db, action="document.reclassify", actor_id=user.id, target_type="document",
                         target_id=doc.id, request=request)
    return _to_out(db, doc)


@router.delete("/{document_id}", status_code=204)
def delete(document_id: str, request: Request, user: User = Depends(require_roles(Role.analyst)),
           db: Session = Depends(get_db)):
    doc = get_authorized_document(db, user, document_id)
    doc_id = doc.id
    try:
        document_service.delete_document(db, doc)
    except Exception:
        audit_service.record(db, action="document.delete", outcome="failure", actor_id=user.id,
                             target_type="document", target_id=doc_id, request=request)
        raise
    audit_service.record(db, action="document.delete", actor_id=user.id, target_type="document", target_id=doc_id,
                         request=request)


@router.delete("/{document_id}/entities/{entity_id}", status_code=204)
def remove_entity(document_id: str, entity_id: str, request: Request,
                  user: User = Depends(require_roles(Role.reviewer)), db: Session = Depends(get_db)):
    ent = db.get(ExtractedEntity, entity_id)
    if ent is None or ent.document_id != document_id:
        raise NotFound("Entity not found")
    ent.removed = True
    db.commit()
    audit_service.record(db, action="entity.remove", actor_id=user.id, target_type="entity", target_id=entity_id,
                         request=request)

