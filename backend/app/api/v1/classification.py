from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.config import PROJECT_DIR
from app.core.errors import AppError, NotFound
from app.db.session import SessionLocal, get_db
from app.models import AuditEvent, ClassificationPrediction, Document, ModelVersion, ReviewRecord, Role, User
from app.schemas import PredictIn, ReviewIn, ReviewItem, TrainIn
from app.services import audit_service, classification_service

router = APIRouter(tags=["classification"])
admin_only = require_roles()
analyst = require_roles(Role.analyst)
reviewer = require_roles(Role.reviewer)


def _mv_out(mv: ModelVersion, full: bool = False) -> dict:
    out = {"id": mv.id, "version": mv.version, "algorithm": mv.algorithm, "is_active": mv.is_active,
           "score_type": mv.score_type, "categories": mv.categories, "dataset_info": mv.dataset_info,
           "created_at": mv.created_at, "headline": {k: mv.metrics.get(k) for k in
                                                     ("accuracy", "macro_f1", "weighted_f1", "n_evaluated")}}
    if full:
        out["metrics"] = mv.metrics
        out["comparison"] = mv.comparison
    return out


@router.post("/classification/predict")
def predict(body: PredictIn, user: User = Depends(analyst), db: Session = Depends(get_db)):
    return {**classification_service.predict_text(db, body.text), "note": (
        "Scores from Logistic Regression are uncalibrated probabilities; SVM scores are decision values, not probabilities.")}


@router.get("/classification/models")
def list_models(user: User = Depends(analyst), db: Session = Depends(get_db)):
    return [_mv_out(m) for m in db.scalars(select(ModelVersion).order_by(ModelVersion.created_at.desc()))]


@router.get("/classification/metrics")
def metrics(user: User = Depends(analyst), db: Session = Depends(get_db)):
    mv = classification_service.active_model_version(db)
    if mv is None:
        raise NotFound("No trained model yet. An administrator can train one from the Classification page.")
    return _mv_out(mv, full=True)


def _train_job(dataset: str, actor_id: str, request_id: str | None) -> None:
    import pandas as pd

    db = SessionLocal()
    try:
        actor = db.get(User, actor_id)
        df = pd.read_csv(PROJECT_DIR / "data" / "sample" / "training_data.csv") if dataset == "sample_csv" else None
        mv = classification_service.train_model(db, df, actor, dataset)
        db.add(AuditEvent(actor_id=actor_id, action="model.train", target_type="model", target_id=mv.id,
                          outcome="success", request_id=request_id, detail=mv.version))
        db.commit()
    except Exception as exc:  # noqa: BLE001 - recorded in the audit trail, never swallowed silently
        db.rollback()
        audit_service.record(db, action="model.train", outcome="failure", actor_id=actor_id, detail=str(exc)[:300])
    finally:
        db.close()


@router.post("/classification/train", status_code=202)
def train(body: TrainIn, request: Request, background: BackgroundTasks, admin: User = Depends(admin_only),
          db: Session = Depends(get_db)):
    audit_service.record(db, action="model.train_requested", actor_id=admin.id, request=request,
                         detail=f"dataset={body.dataset}")
    background.add_task(_train_job, body.dataset, admin.id, getattr(request.state, "request_id", None))
    return {"status": "accepted", "message": "Training started. Refresh the model list in a moment."}


@router.get("/reviews")
def review_queue(page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
                 user: User = Depends(reviewer), db: Session = Depends(get_db)):
    base = (select(ClassificationPrediction, Document).join(Document, Document.id == ClassificationPrediction.document_id)
            .where(ClassificationPrediction.is_current.is_(True), ClassificationPrediction.review_status == "needs_review"))
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.execute(base.order_by(ClassificationPrediction.created_at).offset((page - 1) * page_size)
                      .limit(page_size)).all()
    items = [ReviewItem(document_id=d.id, filename=d.filename, predicted_category=p.category, score=p.score,
                        score_type=p.score_type, model_version=p.model_version,
                        text_preview=(d.extracted_text or "")[:600], created_at=p.created_at) for p, d in rows]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/reviews/{document_id}", status_code=201)
def submit_review(document_id: str, body: ReviewIn, request: Request, user: User = Depends(reviewer),
                  db: Session = Depends(get_db)):
    """The review item id is the document id: each document has at most one open review."""
    try:
        rec = classification_service.submit_review(db, user, document_id, body.decision, body.category, body.note)
    except AppError:
        audit_service.record(db, action="review.submit", outcome="failure", actor_id=user.id, target_type="document",
                             target_id=document_id, request=request)
        raise
    audit_service.record(db, action="review.submit", actor_id=user.id, target_type="document", target_id=document_id,
                         request=request, detail=f"{rec.decision}: {rec.predicted_category} -> {rec.final_category}")
    return {"id": rec.id, "document_id": document_id, "decision": rec.decision, "final_category": rec.final_category}


@router.get("/reviews/history")
def review_history(user: User = Depends(reviewer), db: Session = Depends(get_db)):
    rows = db.scalars(select(ReviewRecord).order_by(ReviewRecord.created_at.desc()).limit(50))
    return [{"id": r.id, "document_id": r.document_id, "decision": r.decision, "predicted": r.predicted_category,
             "final": r.final_category, "note": r.note, "created_at": r.created_at} for r in rows]

