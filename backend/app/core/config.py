"""Application configuration loaded from environment variables.

Maps to the env contract in the architecture spec §9. Provider-agnostic LLM access
(OpenAI / vLLM / llama.cpp / Ollama) via a configurable ``base_url``.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- App ---
    environment: Literal["development", "production", "test"] = "development"
    log_level: str = "INFO"
    log_json: bool = False

    # --- CORS ---
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    # --- LLM (OpenAI-compatible endpoint)
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = "changeme"
    model_fast: str = "gpt-4o-mini"  # generation, translation, article metadata
    model_long_ctx: str = "gpt-4o-mini"  # monograph metadata (long context)
    model_fallback: str = "gpt-4o-mini"  # reserve, up to 3 retries

    # --- Embeddings (local)
    embed_model: str = "all-MiniLM-L6-v2"

    # --- Infrastructure
    database_url: str = "postgresql+asyncpg://laserrag:laserrag@postgres:5432/laserrag"
    chroma_host: str = "chromadb"
    chroma_port: int = 8000
    redis_url: str = "redis://redis:6379/0"

    # --- Auth ---
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 7

    # --- Chat
    chat_history_window: int = 8  # N last turns kept in context

    # --- Uploads ---
    max_upload_mb: int = 50
    allowed_extensions: list[str] = Field(
        default_factory=lambda: ["pdf", "docx", "odt", "txt", "md"]
    )
    upload_dir: str = "/data/uploads"  # where uploaded source files are stored

    # --- Multi-tenancy seam
    default_tenant_id: str = "default"


@lru_cache
def get_settings() -> Settings:
    return Settings()
