import time
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.ratelimit import rate_limit
from app.db.session import get_db
from app.models import Role, SearchLog, User
from app.schemas import SearchHit, SearchQuery, SearchResponse
from app.services import retrieval_service

router = APIRouter(prefix="/search", tags=["search"])
analyst = require_roles(Role.analyst)


def _run(db: Session, user: User, mode: str, q: SearchQuery) -> SearchResponse:
    start = time.monotonic()
    hits, total = retrieval_service.search(db, user, q.query, mode, q.category, q.file_type, q.date_from, q.date_to,
                                           q.page, q.page_size)
    db.add(SearchLog(user_id=user.id, query=q.query[:500], mode=mode, result_count=total,
                     latency_ms=int((time.monotonic() - start) * 1000)))
    db.commit()
    results = [SearchHit(
        chunk_id=h.chunk_id, document_id=h.document_id, filename=h.filename, file_type=h.extension, page=h.page,
        chunk_index=h.chunk_index, excerpt=retrieval_service.excerpt(h.text, h.highlights), highlights=h.highlights,
        score=h.score, keyword_score=h.keyword_score, semantic_score=h.semantic_score, category=h.category,
        created_at=h.created_at) for h in hits]
    return SearchResponse(mode=mode, query=q.query, total=total, page=q.page, page_size=q.page_size, results=results)


@router.get("", response_model=SearchResponse, dependencies=[rate_limit("search")])
def keyword(query: str = Query(min_length=1, max_length=500), category: str | None = None,
            file_type: str | None = Query(default=None, max_length=10), date_from: datetime | None = None,
            date_to: datetime | None = None, page: int = Query(default=1, ge=1, le=100),
            page_size: int = Query(default=10, ge=1, le=50), user: User = Depends(analyst),
            db: Session = Depends(get_db)):
    q = SearchQuery(query=query, category=category, file_type=file_type, date_from=date_from, date_to=date_to,
                    page=page, page_size=page_size)
    return _run(db, user, "keyword", q)


@router.post("/semantic", response_model=SearchResponse, dependencies=[rate_limit("search")])
def semantic(q: SearchQuery, user: User = Depends(analyst), db: Session = Depends(get_db)):
    return _run(db, user, "semantic", q)


@router.post("/hybrid", response_model=SearchResponse, dependencies=[rate_limit("search")])
def hybrid(q: SearchQuery, user: User = Depends(analyst), db: Session = Depends(get_db)):
    return _run(db, user, "hybrid", q)
