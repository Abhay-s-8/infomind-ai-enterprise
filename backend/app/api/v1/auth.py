from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.config import get_settings
from app.core.errors import AppError, Conflict, NotFound
from app.core.ratelimit import rate_limit
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models import Role, User
from app.schemas import LoginIn, RegisterIn, RoleUpdate, TokenOut, UserOut
from app.services import audit_service

router = APIRouter(tags=["auth"])

# Fixed hash used to equalise timing when the email is unknown.
_DUMMY_HASH = hash_password("not-a-real-password")


@router.post("/auth/register", response_model=UserOut, status_code=201, dependencies=[rate_limit("register", 10)])
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    if not get_settings().enable_registration:
        raise AppError("Registration is disabled.", status_code=403, code="registration_disabled")
    if db.scalar(select(User).where(User.email == body.email)):
        raise Conflict("An account with this email already exists.")
    user = User(email=body.email, full_name=body.full_name, password_hash=hash_password(body.password),
                role=Role.analyst.value)
    db.add(user)
    db.commit()
    audit_service.record(db, action="user.register", actor_id=user.id, target_type="user", target_id=user.id,
                         request=request)
    return user


@router.post("/auth/login", response_model=TokenOut, dependencies=[rate_limit("login", 10)])
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    ok = verify_password(body.password, user.password_hash if user else _DUMMY_HASH)
    if not user or not ok or not user.is_active:
        audit_service.record(db, action="auth.login", outcome="failure", actor_id=user.id if user else None,
                             request=request, detail="invalid credentials")
        raise AppError("Invalid email or password.", status_code=401, code="invalid_credentials")
    token, ttl = create_access_token(user.id, user.role)
    audit_service.record(db, action="auth.login", actor_id=user.id, request=request)
    return TokenOut(access_token=token, expires_in=ttl)


@router.post("/auth/logout", status_code=204)
def logout(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Tokens are stateless; the client discards its token. The event is audited."""
    audit_service.record(db, action="auth.logout", actor_id=user.id, request=request)


@router.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.get("/users", response_model=list[UserOut])
def list_users(_: User = Depends(require_roles()), db: Session = Depends(get_db)):
    return list(db.scalars(select(User).order_by(User.created_at)))


@router.patch("/users/{user_id}/role", response_model=UserOut)
def set_role(user_id: str, body: RoleUpdate, request: Request, admin: User = Depends(require_roles()),
             db: Session = Depends(get_db)):
    target = db.get(User, user_id)
    if target is None:
        raise NotFound("User not found")
    if target.id == admin.id and body.role != Role.admin.value:
        raise AppError("Administrators cannot remove their own admin role.", code="self_demotion")
    old, target.role = target.role, body.role
    db.commit()
    audit_service.record(db, action="user.role_change", actor_id=admin.id, target_type="user", target_id=target.id,
                         request=request, detail=f"{old} -> {body.role}")
    return target
