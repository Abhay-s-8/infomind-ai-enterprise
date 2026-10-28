"""Authenticating gateway in front of a local Ollama, so Ollama can be reached through a tunnel without being exposed.

Ollama has no login of its own: anyone who can reach it can run models on your GPU and even delete or pull models.
This gateway listens on the loopback address only (the tunnel connects to it from the same machine) and:
  * requires "Authorization: Bearer <OLLAMA_GATEWAY_KEY>" on every request (constant-time comparison);
  * forwards only the three calls this application makes (chat, embed, list models) and refuses everything else;
  * caps the request size and the number of requests per minute;
  * streams the answer through unchanged, so live answers still stream.

Run:  python -m app.gateway      (settings come from the environment, never from the command line)
  OLLAMA_GATEWAY_KEY       required, at least 32 random characters
  OLLAMA_UPSTREAM          default http://127.0.0.1:11434
  OLLAMA_GATEWAY_PORT      default 11435
"""
import hmac
import logging
import os
import sys
import time
from collections import deque

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.background import BackgroundTask

log = logging.getLogger("infomind.gateway")

ALLOWED = {("POST", "/api/chat"), ("POST", "/api/embed"), ("GET", "/api/tags")}
MIN_KEY_CHARS = 32
MAX_BODY_BYTES = 1_000_000  # five 1,200-character evidence blocks plus a question are a few kilobytes
DEFAULT_PER_MINUTE = 60


def _error(status: int, message: str) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status, headers={"X-Content-Type-Options": "nosniff"})


def create_app(key: str, upstream: str = "http://127.0.0.1:11434", *, per_minute: int = DEFAULT_PER_MINUTE,
               client: httpx.AsyncClient | None = None) -> FastAPI:
    if len(key) < MIN_KEY_CHARS:
        raise ValueError(f"The gateway key must be at least {MIN_KEY_CHARS} characters.")
    secret = key.encode()
    http = client or httpx.AsyncClient(base_url=upstream.rstrip("/"), timeout=httpx.Timeout(300.0, connect=5.0))
    hits: deque[float] = deque()
    app = FastAPI(title="Ollama gateway", docs_url=None, redoc_url=None, openapi_url=None)

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
    async def forward(path: str, request: Request):
        # 1. identity first, so an unauthenticated caller learns nothing about which routes exist
        auth = request.headers.get("authorization", "")
        supplied = auth[7:] if auth[:7].lower() == "bearer " else ""
        if not hmac.compare_digest(supplied.encode(), secret):
            return _error(401, "Unauthorized")
        # 2. only what the application needs
        route = (request.method, "/" + path)
        if route not in ALLOWED:
            return _error(404, "Not found")
        # 3. rate and size limits protect the GPU
        now = time.monotonic()
        while hits and now - hits[0] > 60:
            hits.popleft()
        if len(hits) >= per_minute:
            return _error(429, "Too many requests")
        hits.append(now)
        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > MAX_BODY_BYTES:
            return _error(413, "Request too large")
        body = await request.body()
        if len(body) > MAX_BODY_BYTES:
            return _error(413, "Request too large")
        headers = {"accept-encoding": "identity"}  # the answer is passed through byte for byte, so no compression
        if "content-type" in request.headers:
            headers["content-type"] = request.headers["content-type"]
        try:
            upstream_request = http.build_request(request.method, "/" + path, content=body or None, headers=headers)
            response = await http.send(upstream_request, stream=True)
        except httpx.HTTPError:
            log.warning("Ollama is not reachable at the configured upstream")
            return _error(502, "Ollama is not reachable")
        return StreamingResponse(response.aiter_raw(), status_code=response.status_code,
                                 media_type=response.headers.get("content-type"),
                                 headers={"X-Content-Type-Options": "nosniff"},
                                 background=BackgroundTask(response.aclose))

    return app


def main() -> None:
    import uvicorn

    logging.basicConfig(level=logging.INFO)
    key = os.environ.get("OLLAMA_GATEWAY_KEY", "")
    if len(key) < MIN_KEY_CHARS:
        sys.exit(f"Set OLLAMA_GATEWAY_KEY to a random value of at least {MIN_KEY_CHARS} characters.")
    upstream = os.environ.get("OLLAMA_UPSTREAM", "http://127.0.0.1:11434")
    port = int(os.environ.get("OLLAMA_GATEWAY_PORT", "11435"))
    # loopback only: the tunnel program runs on this machine, nothing else should reach the gateway directly
    uvicorn.run(create_app(key, upstream), host="127.0.0.1", port=port, log_level="info", access_log=False)


if __name__ == "__main__":
    main()
