"""Database-backed job worker: `python -m app.workers.worker`. Safe to run alongside (or instead of) the in-API drain."""
import logging
import time

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services import document_service

log = logging.getLogger("infomind.worker")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    s = get_settings()
    log.info("Worker started (poll=%ss)", s.worker_poll_seconds)
    while True:
        db = SessionLocal()
        try:
            n = document_service.run_pending_jobs(db, limit=10)
        except Exception:  # noqa: BLE001 - keep the loop alive; the failure is logged
            log.exception("Worker iteration failed")
            n = 0
        finally:
            db.close()
        if n == 0:
            time.sleep(s.worker_poll_seconds)


if __name__ == "__main__":
    main()
