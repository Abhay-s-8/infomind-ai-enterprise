from fastapi import Request
from sqlalchemy.orm import Session

from app.models import AuditEvent


def record(db: Session, *, action: str, outcome: str = "success", actor_id: str | None = None,
           target_type: str | None = None, target_id: str | None = None, request: Request | None = None,
           detail: str | None = None) -> AuditEvent:
    """Append an audit event. Never pass passwords, tokens or document content in `detail`."""
    event = AuditEvent(
        actor_id=actor_id, action=action, outcome=outcome, target_type=target_type, target_id=target_id,
        request_id=getattr(request.state, "request_id", None) if request is not None else None,
        detail=(detail or None) and detail[:500],
    )
    db.add(event)
    db.commit()
    return event
