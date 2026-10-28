import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request

from app.core.config import get_settings

_hits: dict[str, deque] = defaultdict(deque)


def reset_rate_limits() -> None:
    _hits.clear()


def rate_limit(bucket: str, per_minute: int | None = None):
    """Sliding-window limiter keyed by bucket + client address (in-process; fine for a single-node prototype)."""

    def dep(request: Request) -> None:
        limit = per_minute or get_settings().rate_limit_per_minute
        key = f"{bucket}:{request.client.host if request.client else 'unknown'}"
        now = time.monotonic()
        q = _hits[key]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= limit:
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again shortly.")
        q.append(now)

    return Depends(dep)
