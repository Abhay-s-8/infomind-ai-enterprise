import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

log = logging.getLogger("infomind")


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, status_code: int | None = None, code: str | None = None):
        super().__init__(message)
        self.message = message
        if status_code:
            self.status_code = status_code
        if code:
            self.code = code


class NotFound(AppError):
    status_code, code = 404, "not_found"


class Forbidden(AppError):
    status_code, code = 403, "forbidden"


class Conflict(AppError):
    status_code, code = 409, "conflict"


class ServiceUnavailable(AppError):
    status_code, code = 503, "service_unavailable"


def _body(request: Request, code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message, "request_id": getattr(request.state, "request_id", None)}}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        return JSONResponse(_body(request, exc.code, exc.message), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        log.exception("Unhandled error request_id=%s", getattr(request.state, "request_id", None))
        return JSONResponse(_body(request, "internal_error", "Internal server error"), status_code=500)
