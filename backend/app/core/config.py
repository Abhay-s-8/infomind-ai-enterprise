from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    app_name: str = "InfoMind AI Enterprise"
    environment: str = "development"  # development | test | production
    api_prefix: str = "/api/v1"

    database_url: str = "sqlite:///./infomind.db"
    qdrant_url: str = "http://localhost:6333"  # ":memory:" for an embedded in-process store
    qdrant_collection_prefix: str = "infomind_chunks"

    ollama_base_url: str = "http://localhost:11434"
    ollama_llm_model: str = "llama3.2:3b"
    ollama_embedding_model: str = "nomic-embed-text"
    ollama_timeout_seconds: float = 120.0
    ollama_num_ctx: int = 4096
    # "ollama" (real embeddings) or "hash" (deterministic CPU-only hashing embedder for dev/tests)
    embedding_provider: str = "ollama"
    embedding_dimensions: int = 768
    embedding_batch_size: int = 16

    jwt_secret: str = "change-me-in-env"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60
    enable_registration: bool = True
    dev_admin_email: str = ""
    dev_admin_password: str = ""

    cors_origins: str = "http://localhost:5173"
    storage_dir: Path = PROJECT_DIR / "data" / "uploads"
    model_dir: Path = PROJECT_DIR / "models"
    max_upload_mb: int = 25
    chunk_size_chars: int = 900
    chunk_overlap_chars: int = 120

    run_worker_in_api: bool = True
    worker_poll_seconds: float = 2.0
    max_job_attempts: int = 3

    rate_limit_per_minute: int = 30
    low_confidence_threshold: float = 0.55
    min_keyword_overlap: float = 0.34  # fraction of query terms found in the best chunk
    min_semantic_score: float = 0.55  # cosine similarity (tune per embedding model)
    rag_top_k: int = 5

    @field_validator("cors_origins")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @field_validator("database_url")
    @classmethod
    def _driver(cls, v: str) -> str:
        """Hosts such as Render hand out `postgres://` / `postgresql://` URLs; this app uses the psycopg 3 driver."""
        v = v.strip()
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix):]
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    def validate_for_production(self) -> None:
        if self.environment == "production":
            if self.jwt_secret in ("change-me-in-env", "", "change-me") or len(self.jwt_secret) < 32:
                raise RuntimeError("JWT_SECRET must be set to a random value of 32+ characters in production")
            if self.dev_admin_password:
                raise RuntimeError("DEV_ADMIN_PASSWORD must not be set in production")


@lru_cache
def get_settings() -> Settings:
    return Settings()
