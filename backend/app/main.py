import logging
import threading
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.security import hash_password
from app.db.session import Base, SessionLocal, engine
from app.models import Role, User

log = logging.getLogger("infomind")


def ensure_dev_admin() -> None:
    s = get_settings()
    if not (s.dev_admin_email and s.dev_admin_password):
        return
    with SessionLocal() as db:
        if not db.scalar(select(User).where(User.email == s.dev_admin_email.lower())):
            db.add(User(email=s.dev_admin_email.lower(), full_name="Development Administrator",
                        password_hash=hash_password(s.dev_admin_password), role=Role.admin.value))
            db.commit()
            log.warning("Created development administrator %s", s.dev_admin_email)


def _worker_loop(stop: threading.Event) -> None:
    from app.services import document_service

    while not stop.wait(get_settings().worker_poll_seconds):
        db = SessionLocal()
        try:
            document_service.run_pending_jobs(db, limit=5)
        except Exception:  # noqa: BLE001
            log.exception("In-process worker iteration failed")
        finally:
            db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    s.validate_for_production()
    if s.environment in ("development", "test"):
        Base.metadata.create_all(engine)  # production schemas are managed by Alembic migrations
    ensure_dev_admin()
    stop = threading.Event()
    if s.run_worker_in_api and s.environment != "test":
        threading.Thread(target=_worker_loop, args=(stop,), daemon=True, name="job-worker").start()
    yield
    stop.set()


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title=s.app_name, version="0.1.0", lifespan=lifespan,
                  docs_url="/docs" if s.environment != "production" else None, redoc_url=None)
    app.add_middleware(CORSMiddleware, allow_origins=s.cors_origin_list, allow_credentials=False,
                       allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["Authorization", "Content-Type"])

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request.state.request_id = request.headers.get("x-request-id", "")[:64] or uuid.uuid4().hex
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    register_error_handlers(app)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        details = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
        return JSONResponse({"error": {"code": "validation_error", "message": "Invalid request", "details": details,
                                       "request_id": request.state.request_id}}, status_code=422)

    app.include_router(api_router, prefix=s.api_prefix)
    return app


app = create_app()
