"""LLM and embedding access. All model calls go through this layer; browsers never reach Ollama directly."""
import hashlib
import json
import math
import re
from collections.abc import Iterator
from functools import lru_cache
from typing import Protocol

import httpx

from app.core.config import get_settings
from app.core.errors import ServiceUnavailable


class Embedder(Protocol):
    name: str
    dimensions: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class LLM(Protocol):
    name: str

    def chat_json(self, system: str, user: str) -> str: ...

    def chat_json_stream(self, system: str, user: str) -> Iterator[str]: ...


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


REJECTED = "The Ollama gateway rejected the request. Check that OLLAMA_API_KEY matches the gateway's key."
PAYMENT = "Ollama requires usage credits for this model (HTTP 402). Choose a model your plan includes, or add credits."
RATE_LIMITED = "Ollama is limiting requests (HTTP 429). Wait a moment and retry."


class OllamaClient:
    def __init__(self, base_url: str, timeout: float, api_key: str = ""):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.api_key = api_key

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

    @staticmethod
    def _http_error(exc: httpx.HTTPStatusError) -> ServiceUnavailable:
        code = exc.response.status_code
        if code in (401, 403):  # never echo the key or the response body
            return ServiceUnavailable(REJECTED)
        if code == 402:
            return ServiceUnavailable(PAYMENT)
        if code == 429:
            return ServiceUnavailable(RATE_LIMITED)
        return ServiceUnavailable(f"Ollama returned HTTP {code}. Is the model pulled?")

    def _post(self, path: str, payload: dict) -> dict:
        try:
            r = httpx.post(f"{self.base_url}{path}", json=payload, headers=self._headers(), timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as exc:
            raise self._http_error(exc) from exc
        except httpx.HTTPError as exc:
            raise ServiceUnavailable("Ollama is not reachable. Start Ollama and pull the configured models.") from exc

    def _stream(self, path: str, payload: dict) -> Iterator[dict]:
        """POST and yield one parsed JSON object per NDJSON line. The timeout applies per read, not to the whole answer."""
        try:
            with httpx.stream("POST", f"{self.base_url}{path}", json=payload, headers=self._headers(),
                              timeout=self.timeout) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if line.strip():
                        yield json.loads(line)
        except httpx.HTTPStatusError as exc:
            raise self._http_error(exc) from exc
        except httpx.HTTPError as exc:
            raise ServiceUnavailable("Ollama is not reachable. Start Ollama and pull the configured models.") from exc
        except json.JSONDecodeError as exc:
            raise ServiceUnavailable("Ollama sent a response that could not be read.") from exc

    def status(self) -> dict:
        try:
            r = httpx.get(f"{self.base_url}/api/tags", headers=self._headers(), timeout=3.0)
            r.raise_for_status()
            return {"reachable": True, "models": [m["name"] for m in r.json().get("models", [])]}
        except (httpx.HTTPError, ValueError):
            return {"reachable": False, "models": []}


class OllamaEmbedder:
    def __init__(self, client: OllamaClient, model: str, dimensions: int, batch_size: int):
        self.client, self.name, self.dimensions, self.batch_size = client, model, dimensions, batch_size

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            data = self.client._post("/api/embed", {"model": self.name, "input": texts[i:i + self.batch_size]})
            vectors = data.get("embeddings") or []
            if len(vectors) != len(texts[i:i + self.batch_size]):
                raise ServiceUnavailable("Ollama returned an unexpected number of embeddings.")
            for v in vectors:
                if len(v) != self.dimensions:
                    raise ServiceUnavailable(
                        f"Embedding dimension {len(v)} does not match configured EMBEDDING_DIMENSIONS={self.dimensions}.")
            out.extend(vectors)
        return out


class HashingEmbedder:
    """Deterministic bag-of-words hashing embedder. Purely lexical (no semantic understanding); intended for
    CPU-only development and tests, and reported as such by /system/models."""

    def __init__(self, dimensions: int = 256):
        self.name, self.dimensions = "hashing-bow", dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        vecs = []
        for text in texts:
            v = [0.0] * self.dimensions
            for tok in tokenize(text):
                h = int.from_bytes(hashlib.md5(tok.encode()).digest()[:8], "big")
                v[h % self.dimensions] += 1.0 if (h >> 63) & 1 else -1.0
            norm = math.sqrt(sum(x * x for x in v)) or 1.0
            vecs.append([x / norm for x in v])
        return vecs


class OllamaLLM:
    def __init__(self, client: OllamaClient, model: str, num_ctx: int):
        self.client, self.name, self.num_ctx = client, model, num_ctx

    def chat_json(self, system: str, user: str) -> str:
        data = self.client._post("/api/chat", {
            "model": self.name, "stream": False, "format": "json",
            "options": {"temperature": 0, "num_ctx": self.num_ctx},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        })
        return data.get("message", {}).get("content", "")

    def chat_json_stream(self, system: str, user: str) -> Iterator[str]:
        for part in self.client._stream("/api/chat", {
            "model": self.name, "stream": True, "format": "json",
            "options": {"temperature": 0, "num_ctx": self.num_ctx},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }):
            piece = part.get("message", {}).get("content", "")
            if piece:
                yield piece


@lru_cache
def get_ollama_client() -> OllamaClient:
    s = get_settings()
    return OllamaClient(s.ollama_base_url, s.ollama_timeout_seconds, s.ollama_api_key)


@lru_cache
def get_embedder() -> Embedder:
    s = get_settings()
    if s.embedding_provider == "hash":
        return HashingEmbedder(min(s.embedding_dimensions, 512))
    return OllamaEmbedder(get_ollama_client(), s.ollama_embedding_model, s.embedding_dimensions, s.embedding_batch_size)


@lru_cache
def get_llm() -> LLM:
    s = get_settings()
    return OllamaLLM(get_ollama_client(), s.ollama_llm_model, s.ollama_num_ctx)


def model_status() -> dict:
    s = get_settings()
    st = get_ollama_client().status()

    def present(model: str) -> bool:
        # "nomic-embed-text" (no tag) matches "nomic-embed-text:latest"
        return any(m == model or (":" not in model and m.split(":")[0] == model) for m in st["models"])

    return {
        "ollama_reachable": st["reachable"],
        "llm": {"model": s.ollama_llm_model, "available": st["reachable"] and present(s.ollama_llm_model)},
        "embedding": {
            "provider": s.embedding_provider,
            "model": get_embedder().name,
            "dimensions": get_embedder().dimensions,
            "available": True if s.embedding_provider == "hash" else (
                st["reachable"] and present(s.ollama_embedding_model)),
            "note": "Lexical hashing embedder: development/testing only." if s.embedding_provider == "hash" else "",
        },
        "installed_models": st["models"],
    }
