from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError, NotFound
from app.ml import synthetic, training
from app.models import (
    ClassificationPrediction,
    Document,
    ModelVersion,
    ReviewRecord,
    User,
    VerifiedClassification,
    _now,
)

_cache: dict[str, training.LoadedModel] = {}


def active_model_version(db: Session) -> ModelVersion | None:
    return db.scalar(select(ModelVersion).where(ModelVersion.is_active.is_(True)).order_by(ModelVersion.created_at.desc()))


def load_model(mv: ModelVersion) -> training.LoadedModel:
    if mv.version not in _cache:
        _cache[mv.version] = training.LoadedModel(mv.artifact_path)
    return _cache[mv.version]


def train_model(db: Session, df=None, actor: User | None = None, dataset_name: str = "synthetic") -> ModelVersion:
    """Explicit, auditable training run. Never invoked automatically from user edits."""
    if df is None:
        df = synthetic.generate()
    try:
        result = training.train_and_select(df, get_settings().model_dir, dataset_name=dataset_name)
    except training.DatasetError as exc:
        raise AppError(str(exc), code="invalid_dataset") from exc
    for old in db.scalars(select(ModelVersion).where(ModelVersion.is_active.is_(True))):
        old.is_active = False
    mv = ModelVersion(
        version=result["version"], algorithm=result["algorithm"], artifact_path=result["artifact_path"],
        categories=result["categories"], metrics=result["metrics"], comparison=result["comparison"],
        dataset_info=result["dataset_info"], score_type=result["score_type"], is_active=True,
        created_by=actor.id if actor else None)
    db.add(mv)
    db.commit()
    return mv


def predict_text(db: Session, text: str) -> dict:
    mv = active_model_version(db)
    if mv is None:
        raise AppError("No trained classification model is available. Train one first.", status_code=409,
                       code="no_model")
    return load_model(mv).predict(text, get_settings().low_confidence_threshold)


def classify_document(db: Session, doc: Document) -> ClassificationPrediction | None:
    """Store a machine prediction. Never touches VerifiedClassification (human labels are never overwritten)."""
    mv = active_model_version(db)
    if mv is None or not doc.extracted_text:
        return None
    pred = load_model(mv).predict(doc.extracted_text[:20000], get_settings().low_confidence_threshold)
    for old in db.scalars(select(ClassificationPrediction).where(
            ClassificationPrediction.document_id == doc.id, ClassificationPrediction.is_current.is_(True))):
        old.is_current = False
    verified = db.get(VerifiedClassification, doc.id)
    row = ClassificationPrediction(
        document_id=doc.id, model_version=pred["model_version"], category=pred["category"], score=pred["score"],
        score_type=pred["score_type"], all_scores=pred["all_scores"],
        review_status="reviewed" if verified else ("needs_review" if pred["low_confidence"] else "accepted"))
    db.add(row)
    db.commit()
    return row


def current_prediction(db: Session, document_id: str) -> ClassificationPrediction | None:
    return db.scalar(select(ClassificationPrediction).where(
        ClassificationPrediction.document_id == document_id, ClassificationPrediction.is_current.is_(True)))


def effective_category(db: Session, document_id: str) -> str | None:
    """Human-verified label wins; otherwise the current machine prediction."""
    v = db.get(VerifiedClassification, document_id)
    if v:
        return v.category
    p = current_prediction(db, document_id)
    return p.category if p else None


def submit_review(db: Session, reviewer: User, document_id: str, decision: str, category: str | None,
                  note: str) -> ReviewRecord:
    doc = db.get(Document, document_id)
    if doc is None:
        raise NotFound("Document not found")
    pred = current_prediction(db, document_id)
    mv = active_model_version(db)
    valid = set(mv.categories) if mv else set()
    if decision == "confirm":
        if pred is None:
            raise AppError("There is no prediction to confirm; supply a category instead.", code="no_prediction")
        final = pred.category
    else:
        if not category:
            raise AppError("A category is required to correct a classification.", code="category_required")
        if valid and category not in valid:
            raise AppError(f"Unknown category '{category}'.", code="unknown_category")
        final = category
    ver = db.get(VerifiedClassification, document_id)
    if ver:
        ver.category, ver.reviewer_id, ver.created_at = final, reviewer.id, _now()
    else:
        db.add(VerifiedClassification(document_id=document_id, category=final, reviewer_id=reviewer.id))
    if pred:
        pred.review_status = "reviewed"
    rec = ReviewRecord(document_id=document_id, prediction_id=pred.id if pred else None, reviewer_id=reviewer.id,
                       decision=decision, predicted_category=pred.category if pred else None, final_category=final,
                       note=note[:2000])
    db.add(rec)
    db.commit()
    return rec
