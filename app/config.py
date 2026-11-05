"""Runtime configuration. Secrets come from env (local) or AWS Secrets Manager (cloud)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    log_level: str = "INFO"

    llm_mode: Literal["mock", "openai"] = "mock"
    embedding_mode: Literal["mock", "openai"] = "mock"
    store_mode: Literal["memory", "supabase"] = "memory"
    action_queue_mode: Literal["inline", "sqs"] = "inline"
    secrets_backend: Literal["env", "aws"] = "env"

    openai_api_key: str = Field(default="", repr=False)
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_timeout_s: float = 20.0

    database_url: str = Field(default="", repr=False)
    db_pool_max: int = 2

    jwt_secret: str = Field(default="", repr=False)
    jwt_jwks_url: str = ""
    jwt_issuer: str = ""
    jwt_audience: str = "authenticated"

    mcp_shared_secret: str = Field(default="", repr=False)
    action_queue_url: str = ""
    aws_region: str = "us-east-1"
    app_secret_id: str = ""

    embedding_dim: int = 1536
    rag_top_k: int = 5
    rag_min_score: float = 0.12
    quick_max_steps: int = 3
    extended_max_steps: int = 8
    approval_ttl_minutes: int = 60


@lru_cache
def get_settings() -> Settings:
    from app.security.secrets import apply_runtime_secrets

    return apply_runtime_secrets(Settings())
