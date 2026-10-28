"""Keyword, semantic and hybrid retrieval. Authorization is applied in the query (owner filter) and re-verified
against the database for every vector hit, so the vector store is never the sole access-control layer."""
import re
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import ClassificationPrediction, Document, DocumentChunk, User, VerifiedClassification
from app.services.embedding_service import get_embedder, tokenize
from app.services.vector_store import get_vector_store

STOPWORDS = set("a an the of to in on for and or is are was were be been what which who whom how when where why "
                "do does did this that these those with by from at as it its about into can could should would "
                "i you we they their our your me my".split())


@dataclass
class Hit:
    chunk_id: str
    document_id: str
    filename: str
    extension: str
    page: int | None
    chunk_index: int
    text: str
    created_at: datetime
    category: str | None = None
    keyword_score: float = 0.0
    semantic_score: float | None = None
    score: float = 0.0
    highlights: list[str] = field(default_factory=list)


def query_terms(query: str) -> list[str]:
    seen, out = set(), []
    for t in tokenize(query):
        if t not in STOPWORDS and len(t) > 1 and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def keyword_overlap(terms: list[str], text: str) -> tuple[float, int]:
    if not terms:
        return 0.0, 0
    toks = tokenize(text)
    tokset = set(toks)
    present = [t for t in terms if t in tokset]
    tf = sum(toks.count(t) for t in present)
    return len(present) / len(terms), tf


def _scope(stmt, user: User):
    return stmt if user.role == "admin" else stmt.where(Document.owner_id == user.id)


def _categories(db: Session, doc_ids: set[str]) -> dict[str, str]:
    if not doc_ids:
        return {}
    out = {p.document_id: p.category for p in db.scalars(select(ClassificationPrediction).where(
        ClassificationPrediction.document_id.in_(doc_ids), ClassificationPrediction.is_current.is_(True)))}
    out.update({v.document_id: v.category for v in db.scalars(
        select(VerifiedClassification).where(VerifiedClassification.document_id.in_(doc_ids)))})
    return out


def _passes(hit: Hit, category: str | None, file_type: str | None, date_from, date_to) -> bool:
    if category and hit.category != category:
        return False
    if file_type and hit.extension != file_type.lower().lstrip("."):
        return False
    created = hit.created_at.replace(tzinfo=None) if hit.created_at.tzinfo else hit.created_at
    if date_from and created < date_from.replace(tzinfo=None):
        return False
    if date_to and created > date_to.replace(tzinfo=None):
        return False
    return True


def _to_hit(chunk: DocumentChunk, doc: Document) -> Hit:
    return Hit(chunk_id=chunk.id, document_id=doc.id, filename=doc.filename, extension=doc.extension,
               page=chunk.page, chunk_index=chunk.chunk_index, text=chunk.text, created_at=doc.created_at)


def keyword_search(db: Session, user: User, query: str, limit: int = 200) -> list[Hit]:
    terms = query_terms(query)
    if not terms:
        return []
    like = [DocumentChunk.text.ilike(f"%{t.replace('%', '').replace('_', '')}%") for t in terms]
    stmt = _scope(select(DocumentChunk, Document).join(Document, Document.id == DocumentChunk.document_id), user)
    rows = db.execute(stmt.where(or_(*like)).limit(2000)).all()
    hits = []
    for chunk, doc in rows:
        overlap, tf = keyword_overlap(terms, chunk.text)
        if overlap == 0:
            continue
        h = _to_hit(chunk, doc)
        h.keyword_score = h.score = round(overlap * 0.8 + min(tf / (len(terms) * 3), 1.0) * 0.2, 4)
        h.highlights = terms
        hits.append(h)
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:limit]


def semantic_search(db: Session, user: User, query: str, limit: int = 50, file_type: str | None = None) -> list[Hit]:
    vec = get_embedder().embed([query])[0]
    owner = None if user.role == "admin" else user.id
    raw = get_vector_store().search(vec, limit, owner, file_type.lower().lstrip(".") if file_type else None)
    if not raw:
        return []
    scores = {cid: s for cid, s, _ in raw}
    stmt = _scope(select(DocumentChunk, Document).join(Document, Document.id == DocumentChunk.document_id)
                  .where(DocumentChunk.id.in_(list(scores))), user)  # DB re-check of authorization
    terms = query_terms(query)
    hits = []
    for chunk, doc in db.execute(stmt).all():
        h = _to_hit(chunk, doc)
        h.semantic_score = h.score = round(scores[chunk.id], 4)
        h.keyword_score = round(keyword_overlap(terms, chunk.text)[0], 4)
        h.highlights = terms
        hits.append(h)
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits


def hybrid_search(db: Session, user: User, query: str, limit: int = 50, file_type: str | None = None) -> list[Hit]:
    kw = keyword_search(db, user, query, limit)
    sem = semantic_search(db, user, query, limit, file_type)
    merged: dict[str, Hit] = {}
    rrf: dict[str, float] = {}
    for ranked in (kw, sem):
        for rank, h in enumerate(ranked, start=1):
            rrf[h.chunk_id] = rrf.get(h.chunk_id, 0.0) + 1.0 / (60 + rank)
            m = merged.setdefault(h.chunk_id, h)
            m.keyword_score = max(m.keyword_score, h.keyword_score)
            if h.semantic_score is not None:
                m.semantic_score = h.semantic_score
    for h in merged.values():
        sem_part = max(0.0, min(h.semantic_score or 0.0, 1.0))
        h.score = round(0.6 * sem_part + 0.4 * h.keyword_score, 4)
    return sorted(merged.values(), key=lambda h: rrf[h.chunk_id], reverse=True)


def search(db: Session, user: User, query: str, mode: str = "hybrid", category: str | None = None,
           file_type: str | None = None, date_from: datetime | None = None, date_to: datetime | None = None,
           page: int = 1, page_size: int = 10) -> tuple[list[Hit], int]:
    fn = {"keyword": keyword_search, "semantic": semantic_search, "hybrid": hybrid_search}[mode]
    hits = fn(db, user, query, 200) if mode == "keyword" else fn(db, user, query, 200, file_type)
    cats = _categories(db, {h.document_id for h in hits})
    for h in hits:
        h.category = cats.get(h.document_id)
    hits = [h for h in hits if _passes(h, category, file_type, date_from, date_to)]
    total = len(hits)
    start = (page - 1) * page_size
    return hits[start:start + page_size], total


def excerpt(text: str, terms: list[str], width: int = 320) -> str:
    low = text.lower()
    pos = min((low.find(t) for t in terms if low.find(t) >= 0), default=0)
    start = max(0, pos - width // 4)
    snippet = text[start:start + width].strip()
    return ("…" if start > 0 else "") + re.sub(r"\s+", " ", snippet) + ("…" if start + width < len(text) else "")
