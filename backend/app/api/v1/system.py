from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models import AuditEvent, EvaluationRun, Role, User
from app.services import analytics_service, classification_service, embedding_service, entity_service
from app.services.vector_store import get_vector_store

router = APIRouter(tags=["system"])
admin_only = require_roles()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/health/ready")
def ready(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:  # noqa: BLE001
        db_ok = False
    qdrant_ok = get_vector_store().healthy()
    models = embedding_service.model_status()
    return {
        "status": "ready" if db_ok else "degraded",
        "database": {"ok": db_ok},
        "vector_store": {"ok": qdrant_ok},
        "ollama": {"ok": models["ollama_reachable"]},
        "llm_available": models["llm"]["available"],
        "embedding_available": models["embedding"]["available"],
    }


@router.get("/system/models")
def system_models(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    mv = classification_service.active_model_version(db)
    return {**embedding_service.model_status(),
            "classifier": {"available": mv is not None, "version": mv.version if mv else None},
            "entity_extraction": {"rules": True, "spacy": entity_service.spacy_available()}}


@router.get("/analytics/overview")
def a_overview(days: int = Query(default=30, ge=1, le=365), user: User = Depends(require_roles(Role.analyst)),
               db: Session = Depends(get_db)):
    out = analytics_service.overview(db, user, days)
    out["system"] = ready(db)
    return out


@router.get("/analytics/documents")
def a_documents(days: int = Query(default=30, ge=1, le=365), user: User = Depends(require_roles(Role.analyst)),
                db: Session = Depends(get_db)):
    return analytics_service.documents(db, user, days)


@router.get("/analytics/classification")
def a_classification(user: User = Depends(require_roles(Role.analyst)), db: Session = Depends(get_db)):
    return analytics_service.classification(db, user)


@router.get("/analytics/search")
def a_search(days: int = Query(default=30, ge=1, le=365), user: User = Depends(require_roles(Role.analyst)),
             db: Session = Depends(get_db)):
    return analytics_service.search(db, user, days)


@router.get("/audit")
def audit_log(action: str | None = None, outcome: str | None = None, page: int = Query(default=1, ge=1),
              page_size: int = Query(default=50, ge=1, le=200), _: User = Depends(admin_only),
              db: Session = Depends(get_db)):
    stmt = select(AuditEvent).order_by(AuditEvent.created_at.desc())
    if action:
        stmt = stmt.where(AuditEvent.action == action)
    if outcome:
        stmt = stmt.where(AuditEvent.outcome == outcome)
    rows = db.scalars(stmt.offset((page - 1) * page_size).limit(page_size))
    return [{"id": e.id, "created_at": e.created_at, "actor_id": e.actor_id, "action": e.action,
             "target_type": e.target_type, "target_id": e.target_id, "outcome": e.outcome,
             "request_id": e.request_id, "detail": e.detail} for e in rows]


@router.get("/evaluations")
def evaluations(user: User = Depends(require_roles(Role.analyst)), db: Session = Depends(get_db)):
    rows = db.scalars(select(EvaluationRun).order_by(EvaluationRun.created_at.desc()).limit(20))
    return [{"id": r.id, "kind": r.kind, "created_at": r.created_at, "synthetic": r.is_synthetic,
             "config": r.config, "results": r.results} for r in rows]
