from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- auth
class RegisterIn(BaseModel):
    email: str = Field(min_length=5, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=10, max_length=128)
    full_name: str = Field(default="", max_length=255)

    @field_validator("email")
    @classmethod
    def lower(cls, v: str) -> str:
        return v.lower()


class LoginIn(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserOut(ORM):
    id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime


class RoleUpdate(BaseModel):
    role: Literal["admin", "analyst", "reviewer"]


# ---- documents
class EventOut(ORM):
    stage: str
    message: str
    created_at: datetime


class PredictionOut(ORM):
    id: str
    category: str
    score: float
    score_type: str
    all_scores: dict
    model_version: str
    review_status: str
    created_at: datetime


class EntityOut(ORM):
    id: str
    text: str
    label: str
    method: str


class DocumentOut(ORM):
    id: str
    filename: str
    extension: str
    mime_type: str
    size_bytes: int
    sha256: str
    status: str
    error_message: str | None
    page_count: int | None
    chunk_count: int
    is_demo: bool
    deletion_state: str
    owner_id: str
    created_at: datetime
    prediction: PredictionOut | None = None
    verified_category: str | None = None
    category: str | None = None


class DocumentDetail(DocumentOut):
    text_preview: str = ""
    events: list[EventOut] = []
    entities: list[EntityOut] = []
    indexed: bool = False


class DocumentList(BaseModel):
    items: list[DocumentOut]
    total: int
    page: int
    page_size: int


class UploadResult(BaseModel):
    document: DocumentOut
    duplicate: bool


class UploadError(BaseModel):
    filename: str
    error: str


class UploadBatch(BaseModel):
    results: list[UploadResult]
    errors: list[UploadError]


# ---- search
class SearchQuery(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    category: str | None = None
    file_type: str | None = Field(default=None, max_length=10)
    date_from: datetime | None = None
    date_to: datetime | None = None
    page: int = Field(default=1, ge=1, le=100)
    page_size: int = Field(default=10, ge=1, le=50)


class SearchHit(BaseModel):
    chunk_id: str
    document_id: str
    filename: str
    file_type: str
    page: int | None
    chunk_index: int
    excerpt: str
    highlights: list[str]
    score: float
    keyword_score: float
    semantic_score: float | None
    category: str | None
    created_at: datetime


class SearchResponse(BaseModel):
    mode: str
    query: str
    total: int
    page: int
    page_size: int
    results: list[SearchHit]
    note: str = "Totals are capped at the top 200 candidates."


# ---- chat
class ChatIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = None


class Citation(BaseModel):
    document_id: str
    filename: str
    page: int | None
    chunk_id: str
    excerpt: str
    score: float | None = None


class MessageOut(ORM):
    id: str
    role: str
    content: str
    citations: list[Citation] = []
    sufficient_evidence: bool | None = None
    latency_ms: int | None = None
    feedback: str | None = None
    created_at: datetime


class ConversationOut(ORM):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationOut):
    messages: list[MessageOut]


class ChatOut(BaseModel):
    conversation_id: str
    message: MessageOut
    retrieval_mode: str
    excluded_suspicious: int = 0
    inference: str = ""


class FeedbackIn(BaseModel):
    feedback: Literal["up", "down"]


# ---- classification / review
class PredictIn(BaseModel):
    text: str = Field(min_length=1, max_length=50000)


class ReviewIn(BaseModel):
    decision: Literal["confirm", "correct"]
    category: str | None = Field(default=None, max_length=128)
    note: str = Field(default="", max_length=2000)


class ReviewItem(BaseModel):
    document_id: str
    filename: str
    predicted_category: str | None
    score: float | None
    score_type: str | None
    model_version: str | None
    text_preview: str
    created_at: datetime


class TrainIn(BaseModel):
    dataset: Literal["synthetic", "sample_csv"] = "synthetic"
