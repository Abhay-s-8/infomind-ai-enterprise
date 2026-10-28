from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWTError
from sqlalchemy.orm import Session

from app.core.errors import Forbidden, NotFound
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import Document, Role, User
from app.services import audit_service

bearer = HTTPBearer(auto_error=False)


def get_current_user(request: Request, creds: HTTPAuthorizationCredentials | None = Depends(bearer),
                     db: Session = Depends(get_db)) -> User:
    unauth = HTTPException(status_code=401, detail="Not authenticated", headers={"WWW-Authenticate": "Bearer"})
    if creds is None:
        raise unauth
    try:
        payload = decode_access_token(creds.credentials)
    except PyJWTError:
        raise unauth from None
    user = db.get(User, payload.get("sub"))
    if user is None or not user.is_active:
        raise unauth
    request.state.user_id = user.id
    return user


def require_roles(*roles: Role):
    allowed = {r.value for r in roles} | {Role.admin.value}

    def dep(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        if user.role not in allowed:
            audit_service.record(db, action="authz.denied", outcome="denied", actor_id=user.id,
                                 request=request, detail=f"{request.method} {request.url.path}")
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return dep


def is_admin(user: User) -> bool:
    return user.role == Role.admin.value


def get_authorized_document(db: Session, user: User, document_id: str) -> Document:
    """Owner or admin only. Returns 404 (not 403) for other users' documents so existence is not revealed."""
    doc = db.get(Document, document_id)
    if doc is None or (doc.owner_id != user.id and not is_admin(user)):
        raise NotFound("Document not found")
    return doc


__all__ = ["get_current_user", "require_roles", "is_admin", "get_authorized_document", "Forbidden"]
