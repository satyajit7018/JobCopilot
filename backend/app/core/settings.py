"""
JobCopilot - Centralized Typed System Settings
Pydantic BaseSettings providing strong type safety, environment variable parsing,
and fail-closed security validations in production environments.
"""

import logging
import os
from pathlib import Path
from typing import List, Optional, Union

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


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
    # No hardcoded default: a real secret must come from the environment. When unset,
    # auth derives an ephemeral per-process secret (non-prod) or fails closed (prod).
    JWT_SECRET: Optional[str] = None
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
    # Local development only: accept unsigned inbound-email webhooks. Ignored in production.
    INBOUND_EMAIL_ALLOW_UNSIGNED: bool = False
    # Bearer token Prometheus must send to scrape /metrics (audit P1-12).
    METRICS_TOKEN: Optional[str] = None

    # LLM Providers (OpenAI & Anthropic)
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    DEFAULT_LLM_PROVIDER: str = "local"  # "openai", "anthropic", "local"
    DEFAULT_LLM_MODEL: str = "gpt-4o-mini"
    LLM_CACHE_ENABLED: bool = True
    LLM_CACHE_TTL_SECONDS: int = 86400  # 24 hours
    LLM_DAILY_TOKEN_LIMIT_FREE: int = 50_000
    LLM_DAILY_TOKEN_LIMIT_PRO: int = 500_000
    LLM_DAILY_TOKEN_LIMIT_ELITE: int = 2_000_000

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
                    logger.debug("settings: failed to parse ALLOWED_ORIGINS as JSON, falling back to comma-separated", exc_info=True)
                    pass
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @model_validator(mode="after")
    def validate_production_fail_closed(self) -> "Settings":
        """Fail-closed secret/config validation for production.

        Generalizes the JWT/master-key checks into a single config-aware audit:
        each secret is required only when the active configuration actually uses
        it (S3 creds only when storing to S3, a cloud LLM key only when that
        provider is selected, etc.), and every problem is reported at once so a
        misconfigured deploy fails immediately with a complete list.
        """
        _KNOWN_BAD_JWT_SECRET = "jobcopilot-super-secret-saas-jwt-signing-key-32b"
        if self.ENV.lower() != "production":
            return self

        errors: list[str] = []

        # --- Always required ---
        if not self.JWT_SECRET or self.JWT_SECRET == _KNOWN_BAD_JWT_SECRET or len(self.JWT_SECRET) < 32:
            errors.append(
                "JWT_SECRET must be a cryptographically secure string of at least 32 characters "
                "(and not the shipped placeholder)."
            )
        if not self.JOBCOPILOT_MASTER_KEY:
            errors.append("JOBCOPILOT_MASTER_KEY is required for the AES credential vault.")

        # Users cannot sign in without a Google client id (the only production
        # login path — the dev email/demo path is disabled in prod).
        if not self.INBOUND_EMAIL_WEBHOOK_SECRET:
            errors.append("INBOUND_EMAIL_WEBHOOK_SECRET is required; the inbound email webhook is public.")

        if not self.GOOGLE_OAUTH_CLIENT_ID:
            errors.append("GOOGLE_OAUTH_CLIENT_ID is required — it is the only production sign-in path.")

        # --- Conditionally required, by active configuration ---
        if self.DB_MODE.lower() == "postgres" and not (self.DATABASE_URL or "").startswith("postgres"):
            errors.append("DB_MODE=postgres requires a postgres:// DATABASE_URL.")

        if self.STORAGE_BACKEND.lower() in ("s3", "r2"):
            for name in ("S3_BUCKET_NAME", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"):
                if not getattr(self, name):
                    errors.append(f"{name} is required when STORAGE_BACKEND={self.STORAGE_BACKEND}.")

        provider = self.DEFAULT_LLM_PROVIDER.lower()
        if provider == "openai" and not self.OPENAI_API_KEY:
            errors.append("OPENAI_API_KEY is required when DEFAULT_LLM_PROVIDER=openai.")
        if provider == "anthropic" and not self.ANTHROPIC_API_KEY:
            errors.append("ANTHROPIC_API_KEY is required when DEFAULT_LLM_PROVIDER=anthropic.")

        if self.USE_CELERY and "localhost" in self.REDIS_URL:
            errors.append("USE_CELERY=true requires a non-localhost REDIS_URL in production.")

        # Stripe: only enforced once billing is wired (a secret key is present),
        # in which case the webhook secret must accompany it.
        if self.STRIPE_SECRET_KEY and not self.STRIPE_WEBHOOK_SECRET:
            errors.append("STRIPE_WEBHOOK_SECRET is required when STRIPE_SECRET_KEY is set.")

        if errors:
            raise ValueError(
                "FATAL: production configuration is incomplete:\n  - " + "\n  - ".join(errors)
            )
        return self

    @property
    def is_production(self) -> bool:
        """True when running under the production environment."""
        return self.ENV.lower() == "production"

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
