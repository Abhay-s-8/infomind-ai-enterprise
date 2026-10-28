"""Qdrant wrapper. Collections are versioned by embedding model and dimension so incompatible vectors never mix."""
import atexit
import re
from functools import lru_cache

from qdrant_client import QdrantClient, models

from app.core.config import get_settings
from app.core.errors import ServiceUnavailable


def collection_name(model: str, dim: int) -> str:
    safe = re.sub(r"[^a-z0-9]+", "_", model.lower()).strip("_")
    return f"{get_settings().qdrant_collection_prefix}_{safe}_{dim}"


@lru_cache
def _client() -> QdrantClient:
    url = get_settings().qdrant_url
    if url == ":memory:":
        client = QdrantClient(location=":memory:")
    elif url.startswith("path:"):  # embedded on-disk mode (single process only): QDRANT_URL=path:./data/qdrant
        client = QdrantClient(path=url[5:])
    else:
        client = QdrantClient(url=url, timeout=10)
    atexit.register(client.close)  # avoids noisy interpreter-shutdown errors from embedded mode
    return client


class VectorStore:
    def __init__(self, model: str, dim: int):
        self.client, self.dim = _client(), dim
        self.collection = collection_name(model, dim)

    def _wrap(self, fn, *a, **kw):
        try:
            return fn(*a, **kw)
        except Exception as exc:  # qdrant raises a variety of transport/response errors
            raise ServiceUnavailable("The vector database is unavailable.") from exc

    def ensure_collection(self) -> None:
        def go():
            if not self.client.collection_exists(self.collection):
                self.client.create_collection(
                    self.collection, vectors_config=models.VectorParams(size=self.dim, distance=models.Distance.COSINE))
                if get_settings().qdrant_url.startswith("http"):  # embedded modes ignore payload indexes
                    for f in ("owner_id", "document_id", "extension"):
                        self.client.create_payload_index(self.collection, f, models.PayloadSchemaType.KEYWORD)
        self._wrap(go)

    def delete_document(self, document_id: str) -> None:
        def go():
            if self.client.collection_exists(self.collection):
                self.client.delete(self.collection, models.FilterSelector(filter=models.Filter(must=[
                    models.FieldCondition(key="document_id", match=models.MatchValue(value=document_id))])))
        self._wrap(go)

    def upsert(self, points: list[tuple[str, list[float], dict]]) -> None:
        self.ensure_collection()
        self._wrap(self.client.upsert, self.collection, points=[
            models.PointStruct(id=pid, vector=vec, payload=payload) for pid, vec, payload in points])

    def search(self, vector: list[float], limit: int, owner_id: str | None, extension: str | None = None,
               ) -> list[tuple[str, float, dict]]:
        """owner_id=None means unrestricted (admin only)."""
        self.ensure_collection()
        must = []
        if owner_id is not None:
            must.append(models.FieldCondition(key="owner_id", match=models.MatchValue(value=owner_id)))
        if extension:
            must.append(models.FieldCondition(key="extension", match=models.MatchValue(value=extension)))
        res = self._wrap(self.client.query_points, self.collection, query=vector, limit=limit,
                         query_filter=models.Filter(must=must) if must else None, with_payload=True)
        return [(str(p.id), float(p.score), p.payload or {}) for p in res.points]

    def count(self) -> int | None:
        try:
            return self.client.count(self.collection).count if self.client.collection_exists(self.collection) else 0
        except Exception:
            return None

    def healthy(self) -> bool:
        try:
            self.client.get_collections()
            return True
        except Exception:
            return False


def get_vector_store() -> VectorStore:
    from app.services.embedding_service import get_embedder

    e = get_embedder()
    return VectorStore(e.name, e.dimensions)
