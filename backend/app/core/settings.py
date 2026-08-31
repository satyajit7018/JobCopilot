"""
JobCopilot - Centralized Typed System Settings
Pydantic BaseSettings providing strong type safety, environment variable parsing,
and fail-closed security validations in production environments.
"""

import os
from pathlib import Path
from typing import List, Optional, Union
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False
    )

    # Environment
    ENV: str = "development"
    DEBUG: bool = False

    # Paths & Storage
    JOBCOPILOT_DATA_DIR: Optional[str] = None
    STORAGE_BACKEND: str = "local"  # "local", "s3", "r2"
    S3_BUCKET_NAME: Optional[str] = None
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "us-east-1"
    S3_ENDPOINT_URL: Optional[str] = None

    # Database
    DATABASE_URL: Optional[str] = None
    DB_MODE: str = "sqlite"  # "sqlite" or "postgres"

    # Cryptography & Master Vault
    JOBCOPILOT_MASTER_KEY: Optional[str] = None

    # Authentication & JWT
    JWT_SECRET: str = "jobcopilot-super-secret-saas-jwt-signing-key-32b"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    PASSWORD_MIN_LENGTH: int = 12

    # CORS & Networking
    ALLOWED_ORIGINS: Union[List[str], str] = [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ]
    API_PORT: int = 8000
    FRONTEND_PORT: int = 5173
    CDP_PORT: int = 9222

    # Background Tasks & Cache (Redis & Celery)
    REDIS_URL: str = "redis://localhost:6379/0"
    USE_CELERY: bool = False

    # Stripe Billing
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    STRIPE_PRO_PRICE_ID: str = "price_pro_monthly"
    STRIPE_ELITE_PRICE_ID: str = "price_elite_monthly"

    # OAuth & SSO
    GOOGLE_OAUTH_CLIENT_ID: Optional[str] = None

    # SMTP / Inbound Email
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: str = "noreply@jobcopilot.app"
    SMTP_TLS: bool = True
    INBOUND_EMAIL_WEBHOOK_SECRET: Optional[str] = None

    # LLM Providers (OpenAI & Anthropic)
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    DEFAULT_LLM_PROVIDER: str = "local"  # "openai", "anthropic", "local"
    DEFAULT_LLM_MODEL: str = "gpt-4o-mini"

    # Stealth Bot & Proxy
    PROXY_PASSWORD: str = "secret"

    # Observability
    SENTRY_DSN: Optional[str] = None

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v):
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @model_validator(mode="after")
    def validate_production_fail_closed(self) -> "Settings":
        """Enforces critical secrets in production (fail-closed architecture)."""
        if self.ENV.lower() == "production":
            if not self.JWT_SECRET or self.JWT_SECRET == "jobcopilot-super-secret-saas-jwt-signing-key-32b" or len(self.JWT_SECRET) < 32:
                raise ValueError(
                    "FATAL: In production, JWT_SECRET must be set to a cryptographically secure string of at least 32 characters."
                )
            if not self.JOBCOPILOT_MASTER_KEY:
                raise ValueError(
                    "FATAL: In production, JOBCOPILOT_MASTER_KEY environment variable is required for AES credential vault."
                )
        return self

    @property
    def app_dir(self) -> Path:
        base = Path(self.JOBCOPILOT_DATA_DIR) if self.JOBCOPILOT_DATA_DIR else Path(os.path.expanduser("~/.jobcopilot"))
        base.mkdir(parents=True, exist_ok=True)
        return base

    @property
    def db_path(self) -> Path:
        return self.app_dir / "jobcopilot.db"

    @property
    def vault_enc_path(self) -> Path:
        return self.app_dir / "vault.enc"

    @property
    def profiles_dir(self) -> Path:
        p = self.app_dir / "profiles"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def resumes_dir(self) -> Path:
        p = self.app_dir / "resumes"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def backups_dir(self) -> Path:
        p = self.app_dir / "backups"
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()
