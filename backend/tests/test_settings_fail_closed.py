"""
JobCopilot - Production fail-closed configuration validation.
Verifies the config-aware secret validation in Settings (P1-3): each secret is
required only when the active configuration uses it, and a valid prod config boots.
"""

import pytest

from app.core.settings import Settings

# A minimal, fully-valid production config (local storage, local LLM, sqlite).
BASE_PROD = dict(
    _env_file=None,
    ENV="production",
    JWT_SECRET="x" * 40,
    JOBCOPILOT_MASTER_KEY="master-key-value",
    GOOGLE_OAUTH_CLIENT_ID="123.apps.googleusercontent.com",
)


def _make(**overrides):
    return Settings(**{**BASE_PROD, **overrides})


def test_valid_minimal_production_config_boots():
    s = _make()
    assert s.is_production is True


def test_missing_jwt_secret_fails():
    with pytest.raises(ValueError, match="JWT_SECRET"):
        _make(JWT_SECRET=None)


def test_placeholder_jwt_secret_fails():
    with pytest.raises(ValueError, match="JWT_SECRET"):
        _make(JWT_SECRET="jobcopilot-super-secret-saas-jwt-signing-key-32b")


def test_missing_master_key_fails():
    with pytest.raises(ValueError, match="JOBCOPILOT_MASTER_KEY"):
        _make(JOBCOPILOT_MASTER_KEY=None)


def test_missing_google_client_id_fails():
    with pytest.raises(ValueError, match="GOOGLE_OAUTH_CLIENT_ID"):
        _make(GOOGLE_OAUTH_CLIENT_ID=None)


def test_s3_backend_requires_aws_credentials():
    with pytest.raises(ValueError, match="AWS_ACCESS_KEY_ID"):
        _make(STORAGE_BACKEND="s3")
    # ...but with the creds present it boots.
    s = _make(
        STORAGE_BACKEND="s3",
        S3_BUCKET_NAME="b",
        AWS_ACCESS_KEY_ID="ak",
        AWS_SECRET_ACCESS_KEY="sk",
    )
    assert s.STORAGE_BACKEND == "s3"


def test_openai_provider_requires_key():
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        _make(DEFAULT_LLM_PROVIDER="openai")


def test_postgres_mode_requires_postgres_url():
    with pytest.raises(ValueError, match="DATABASE_URL"):
        _make(DB_MODE="postgres", DATABASE_URL=None)


def test_stripe_secret_without_webhook_fails():
    with pytest.raises(ValueError, match="STRIPE_WEBHOOK_SECRET"):
        _make(STRIPE_SECRET_KEY="sk_live_x")


def test_all_errors_reported_together():
    """A deploy missing several secrets fails with every problem listed at once."""
    with pytest.raises(ValueError) as exc:
        _make(JOBCOPILOT_MASTER_KEY=None, GOOGLE_OAUTH_CLIENT_ID=None, DEFAULT_LLM_PROVIDER="anthropic")
    msg = str(exc.value)
    assert "JOBCOPILOT_MASTER_KEY" in msg
    assert "GOOGLE_OAUTH_CLIENT_ID" in msg
    assert "ANTHROPIC_API_KEY" in msg
