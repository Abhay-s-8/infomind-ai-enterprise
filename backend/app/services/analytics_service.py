"""Analytics computed from real rows. Everything is scoped to the caller (admins see all users)."""
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    ChatMessage,
    ClassificationPrediction,
    Conversation,
    Document,
    EvaluationRun,
    ModelVersion,
    ProcessingJob,
    SearchLog,
    User,
    VerifiedClassification,
)


def _doc_scope(stmt, user: User):
    return stmt if user.role == "admin" else stmt.where(Document.owner_id == user.id)


def _since(days: int) -> datetime:
    return datetime.now(UTC) - timedelta(days=days)


def _category_counts(db: Session, user: User) -> dict[str, int]:
    docs = db.execute(_doc_scope(select(Document.id), user)).scalars().all()
    if not docs:
        return {}
    cats: dict[str, str] = {p.document_id: p.category for p in db.scalars(select(ClassificationPrediction).where(
        ClassificationPrediction.document_id.in_(docs), ClassificationPrediction.is_current.is_(True)))}
    cats.update({v.document_id: v.category for v in db.scalars(
        select(VerifiedClassification).where(VerifiedClassification.document_id.in_(docs)))})
    out: dict[str, int] = {}
    for c in cats.values():
        out[c] = out.get(c, 0) + 1
    return out


def overview(db: Session, user: User, days: int = 30) -> dict:
    status_rows = db.execute(_doc_scope(select(Document.status, func.count()).group_by(Document.status), user)).all()
    by_status = {s: n for s, n in status_rows}
    total = sum(by_status.values())
    done, failed = by_status.get("completed", 0), by_status.get("failed", 0)
    pending = sum(by_status.get(s, 0) for s in ("uploaded", "queued", "extracting", "chunking", "embedding",
                                                 "classifying", "indexed"))
    recent = db.scalars(_doc_scope(select(Document), user).order_by(Document.created_at.desc()).limit(5)).all()
    sl = select(SearchLog).order_by(SearchLog.created_at.desc()).limit(5)
    if user.role != "admin":
        sl = sl.where(SearchLog.user_id == user.id)
    ql = (select(ChatMessage, Conversation).join(Conversation, Conversation.id == ChatMessage.conversation_id)
          .where(ChatMessage.role == "user").order_by(ChatMessage.created_at.desc()).limit(5))
    if user.role != "admin":
        ql = ql.where(Conversation.owner_id == user.id)
    needs_review = db.scalar(select(func.count()).select_from(ClassificationPrediction).where(
        ClassificationPrediction.is_current.is_(True), ClassificationPrediction.review_status == "needs_review")) or 0
    return {
        "totals": {"documents": total, "completed": done, "pending": pending, "failed": failed,
                   "pending_reviews": needs_review if user.role in ("admin", "reviewer") else None},
        "processing_success_rate": round(done / (done + failed), 4) if (done + failed) else None,
        "by_status": by_status,
        "classification_distribution": _category_counts(db, user),
        "recent_uploads": [{"id": d.id, "filename": d.filename, "status": d.status, "created_at": d.created_at,
                            "is_demo": d.is_demo} for d in recent],
        "recent_searches": [{"query": s.query, "mode": s.mode, "results": s.result_count, "created_at": s.created_at}
                            for s in db.scalars(sl)],
        "recent_questions": [{"question": m.content[:200], "created_at": m.created_at}
                             for m, _ in db.execute(ql).all()],
        "has_demo_data": bool(db.scalar(_doc_scope(select(func.count()).select_from(Document), user)
                                        .where(Document.is_demo.is_(True)))),
        "window_days": days,
        "data_kind": "measured",
    }


def documents(db: Session, user: User, days: int = 30) -> dict:
    day = func.date(Document.created_at)
    over_time = db.execute(_doc_scope(select(day, func.count()).where(Document.created_at >= _since(days))
                                      .group_by(day).order_by(day), user)).all()
    by_type = db.execute(_doc_scope(select(Document.extension, func.count()).group_by(Document.extension), user)).all()
    jobs = db.execute(select(func.avg(ProcessingJob.duration_ms), func.count()).where(
        ProcessingJob.duration_ms.is_not(None))).one()
    return {
        "uploads_over_time": [{"date": str(d), "count": n} for d, n in over_time],
        "by_file_type": [{"type": t, "count": n} for t, n in by_type],
        "by_category": [{"category": c, "count": n} for c, n in _category_counts(db, user).items()],
        "avg_processing_ms": round(jobs[0]) if jobs[0] is not None else None,
        "processing_jobs_measured": jobs[1],
        "data_kind": "measured",
    }


def classification(db: Session, user: User) -> dict:
    mv = db.scalar(select(ModelVersion).where(ModelVersion.is_active.is_(True)))
    pending = db.scalar(select(func.count()).select_from(ClassificationPrediction).where(
        ClassificationPrediction.is_current.is_(True), ClassificationPrediction.review_status == "needs_review")) or 0
    out = {"pending_reviews": pending, "model": None, "data_kind": "offline_evaluation"}
    if mv:
        out["model"] = {
            "version": mv.version, "algorithm": mv.algorithm, "trained_at": mv.dataset_info.get("trained_at"),
            "dataset_size": mv.dataset_info.get("total"),
            "synthetic_data": mv.dataset_info.get("name") == "synthetic",
            "comparison": {k: {"macro_f1": v["test"]["macro_f1"], "accuracy": v["test"]["accuracy"],
                               "weighted_f1": v["test"]["weighted_f1"]} for k, v in mv.comparison.items()},
            "per_class_f1": {c: m["f1"] for c, m in mv.metrics["per_class"].items()},
            "confusion_matrix": mv.metrics["confusion_matrix"],
        }
    return out


def search(db: Session, user: User, days: int = 30) -> dict:
    day = func.date(SearchLog.created_at)
    base = lambda stmt: stmt if user.role == "admin" else stmt.where(SearchLog.user_id == user.id)  # noqa: E731
    per_day = db.execute(base(select(day, func.count()).where(SearchLog.created_at >= _since(days))
                              .group_by(day).order_by(day))).all()
    modes = db.execute(base(select(SearchLog.mode, func.count(), func.avg(SearchLog.latency_ms))
                            .group_by(SearchLog.mode))).all()
    ev = db.scalar(select(EvaluationRun).where(EvaluationRun.kind == "retrieval").order_by(EvaluationRun.created_at.desc()))
    return {
        "searches_per_day": [{"date": str(d), "count": n} for d, n in per_day],
        "by_mode": [{"mode": m, "count": n, "avg_latency_ms": round(a) if a is not None else None}
                    for m, n, a in modes],
        "retrieval_evaluation": ({"created_at": ev.created_at, "synthetic": ev.is_synthetic, **ev.results}
                                 if ev else None),
        "data_kind": "measured",
    }
