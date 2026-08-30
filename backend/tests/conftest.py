"""
Pytest Fixtures & Configuration for JobCopilot Test Suite
Provides authenticated TestClient fixtures and multi-tenant database isolations.
"""

import os
import pytest
from datetime import timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import db
from app.api.auth import create_jwt_token
from app.core.models import User, UserRole


@pytest.fixture(scope="session")
def client() -> TestClient:
    """Unauthenticated standard TestClient."""
    return TestClient(app)


def _create_authenticated_client(user_id: str, email: str, role: str = "PRO") -> TestClient:
    existing = db.get_user_by_id(user_id)
    if not existing:
        user = User(
            user_id=user_id,
            email=email,
            password_hash="test_hash",
            full_name=f"User {user_id}",
            role=UserRole(role),
            is_active=True
        )
        db.create_user(user)

    token = create_jwt_token(
        {"sub": user_id, "email": email, "role": role, "type": "access"},
        timedelta(minutes=60)
    )
    tc = TestClient(app)
    tc.headers["Authorization"] = f"Bearer {token}"
    return tc


@pytest.fixture(scope="session")
def auth_client() -> TestClient:
    """Pre-authenticated TestClient carrying valid Bearer JWT access token."""
    return _create_authenticated_client("usr_test_tenant_a", "test_candidate_a@jobcopilot.test", "PRO")


@pytest.fixture(scope="session")
def tenant_a_client() -> TestClient:
    """Tenant A TestClient."""
    return _create_authenticated_client("usr_tenant_a", "tenant_a@jobcopilot.test", "PRO")


@pytest.fixture(scope="session")
def tenant_b_client() -> TestClient:
    """Tenant B TestClient."""
    return _create_authenticated_client("usr_tenant_b", "tenant_b@jobcopilot.test", "FREE")
