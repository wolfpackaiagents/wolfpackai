"""Central configuration for the AMP. Read from the environment with pydantic-settings."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Wolfpack AMP"
    environment: str = "development"

    database_url: str = "postgresql+psycopg://wolfpack:wolfpack@localhost:5439/wolfpack"
    redis_url: str = "redis://localhost:6382/0"
    rate_limit_backend: Literal["memory", "redis"] = "memory"
    rate_limit_redis_prefix: str = "wolfpack:rate-limit"

    admin_api_key: str = "dev-admin-key-change-me"
    jwt_secret: str = "change-me-jwt-secret"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 1440
    # Required to create, rotate, or decrypt database-backed provider secrets.
    provider_secrets_master_key: str = ""

    minio_endpoint: str = "http://localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "wolfpack-events"

    ingestion_batch_max_mb: int = 3
    ingestion_job_max_attempts: int = 3
    ingestion_job_lock_seconds: int = 300
    ingestion_worker_poll_seconds: float = 1.0
    ingestion_dispatcher: Literal["local", "inngest"] = "local"

    api_rate_limit_requests: int = Field(default=120, ge=1)
    api_rate_limit_window_seconds: int = Field(default=60, ge=1)
    trace_export_max_records: int = Field(default=1000, ge=1, le=10_000)
    mesh_heartbeat_ttl_seconds: int = Field(default=90, ge=1, le=86_400)
    scheduler_lease_seconds: int = Field(default=300, ge=1, le=86_400)
    scheduler_deadline_seconds: int = Field(default=3600, ge=1, le=604_800)
    scheduler_poll_seconds: float = Field(default=1.0, ge=0.1)
    scheduler_http_allowed_hosts: str = ""
    scheduler_allow_insecure_http: bool = False
    scheduler_dispatch_secret: str = ""
    scheduler_callback_secret: str = ""
    scheduler_callback_max_age_seconds: int = Field(default=300, ge=1, le=86_400)
    scheduler_dispatcher: Literal["local", "inngest"] = "local"

    price_update_interval_hours: float = Field(default=6.0, ge=0.1, le=168)

    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_webhook_secret: str = ""
    telegram_allowed_chat_ids: str = ""
    telegram_registration_id: str = ""
    telegram_delivery_attempts: int = Field(default=3, ge=1, le=10)

    slack_enabled: bool = False
    slack_bot_token: str = ""
    slack_signing_secret: str = ""
    slack_allowed_team_ids: str = ""
    slack_registration_id: str = ""
    slack_replay_window_seconds: int = Field(default=300, ge=1, le=3600)

    discord_enabled: bool = False
    discord_bot_token: str = ""
    discord_public_key: str = ""
    discord_allowed_guild_ids: str = ""
    discord_registration_id: str = ""

    inngest_app_id: str = "wolfpack-amp"
    inngest_dev: bool = False
    inngest_event_key: str | None = None
    inngest_signing_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
