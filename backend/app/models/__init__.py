"""ORM models. IDs are string UUIDs for portability across PostgreSQL and SQLite (tests)."""
import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class Role(enum.StrEnum):
    admin = "admin"
    analyst = "analyst"
    reviewer = "reviewer"


class DocStatus(enum.StrEnum):
    uploaded = "uploaded"
    queued = "queued"
    extracting = "extracting"
    chunking = "chunking"
    embedding = "embedding"
    classifying = "classifying"
    indexed = "indexed"
    completed = "completed"
    failed = "failed"


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class User(Base, Timestamped):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default=Role.analyst.value)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Document(Base, Timestamped):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("owner_id", "sha256", name="uq_document_owner_hash"),
                      Index("ix_documents_owner_status", "owner_id", "status"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    filename: Mapped[str] = mapped_column(String(512))
    storage_id: Mapped[str] = mapped_column(String(64), unique=True)
    extension: Mapped[str] = mapped_column(String(10), index=True)
    mime_type: Mapped[str] = mapped_column(String(128))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(20), default=DocStatus.uploaded.value, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    deletion_state: Mapped[str] = mapped_column(String(20), default="active")  # active | delete_failed
    owner: Mapped[User] = relationship()
    chunks: Mapped[list["DocumentChunk"]] = relationship(cascade="all, delete-orphan", back_populates="document")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (UniqueConstraint("document_id", "chunk_index", name="uq_chunk_index"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)  # also the Qdrant point id
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text: Mapped[str] = mapped_column(Text)
    document: Mapped[Document] = relationship(back_populates="chunks")


class ProcessingJob(Base, Timestamped):
    __tablename__ = "processing_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)  # pending|running|done|failed
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ProcessingEvent(Base):
    __tablename__ = "processing_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    stage: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ModelVersion(Base):
    __tablename__ = "model_versions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    version: Mapped[str] = mapped_column(String(64), unique=True)
    algorithm: Mapped[str] = mapped_column(String(64))
    artifact_path: Mapped[str] = mapped_column(String(512))
    categories: Mapped[list] = mapped_column(JSON)
    metrics: Mapped[dict] = mapped_column(JSON)
    comparison: Mapped[dict] = mapped_column(JSON)
    dataset_info: Mapped[dict] = mapped_column(JSON)
    score_type: Mapped[str] = mapped_column(String(32))  # probability_uncalibrated | decision_score
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ClassificationPrediction(Base):
    __tablename__ = "classification_predictions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    model_version: Mapped[str] = mapped_column(String(64))
    category: Mapped[str] = mapped_column(String(128), index=True)
    score: Mapped[float] = mapped_column(Float)
    score_type: Mapped[str] = mapped_column(String(32))
    all_scores: Mapped[dict] = mapped_column(JSON)
    review_status: Mapped[str] = mapped_column(String(20), default="accepted", index=True)  # needs_review|accepted|reviewed
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class VerifiedClassification(Base):
    __tablename__ = "verified_classifications"
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    category: Mapped[str] = mapped_column(String(128), index=True)
    reviewer_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ReviewRecord(Base):
    __tablename__ = "review_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    prediction_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reviewer_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(16))  # confirm | correct
    predicted_category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    final_category: Mapped[str] = mapped_column(String(128))
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ExtractedEntity(Base):
    __tablename__ = "extracted_entities"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    chunk_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    text: Mapped[str] = mapped_column(String(512))
    label: Mapped[str] = mapped_column(String(32), index=True)
    method: Mapped[str] = mapped_column(String(16))  # rule | spacy
    removed: Mapped[bool] = mapped_column(Boolean, default=False)


class Conversation(Base, Timestamped):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255), default="New conversation")
    messages: Mapped[list["ChatMessage"]] = relationship(cascade="all, delete-orphan", order_by="ChatMessage.created_at")


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[list] = mapped_column(JSON, default=list)
    sufficient_evidence: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feedback: Mapped[str | None] = mapped_column(String(8), nullable=True)  # up | down
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    target_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    outcome: Mapped[str] = mapped_column(String(16))  # success | failure | denied
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[str | None] = mapped_column(String(512), nullable=True)


class SearchLog(Base):
    __tablename__ = "search_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    query: Mapped[str] = mapped_column(String(512))
    mode: Mapped[str] = mapped_column(String(16))
    result_count: Mapped[int] = mapped_column(Integer)
    latency_ms: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    kind: Mapped[str] = mapped_column(String(32), index=True)  # classification | retrieval | rag
    config: Mapped[dict] = mapped_column(JSON)
    results: Mapped[dict] = mapped_column(JSON)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
