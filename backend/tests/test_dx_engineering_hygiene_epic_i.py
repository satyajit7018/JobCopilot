"""
Unit & Integration Tests for Phase P3 Epic I: Engineering Hygiene & Developer Experience (DX)
Validates:
1. One API address: everything under `/api/`, nothing under `/api/v1/`, no deprecation headers
2. The generated OpenAPI specification (`docs/openapi.json`)
3. Architecture Decision Records (ADRs 0001-0004) and CONTRIBUTING.md structure
4. Configuration validation for `pyproject.toml` and `.pre-commit-config.yaml`
"""

import json
import yaml
import tomli
from pathlib import Path
from datetime import timedelta
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import db
from app.core.models import User
from app.api.auth import create_jwt_token


BASE_DIR = Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers():
    test_user_id = "user_epic_i_test"
    email = "epici_test@example.com"
    user = User(
        user_id=test_user_id,
        email=email,
        password_hash="testhash123",
        role="PRO",
        is_active=True
    )
    db.create_user(user)
    token = create_jwt_token(
        {"sub": test_user_id, "email": email, "role": "PRO", "type": "access"},
        timedelta(minutes=30)
    )
    return {"Authorization": f"Bearer {token}", "user_id": test_user_id}


def test_api_is_served_at_one_address(client, auth_headers):
    """The API lives under /api only: the old /api/v1 copy is gone and nothing is marked deprecated."""
    headers = {"Authorization": auth_headers["Authorization"]}

    res = client.get("/api/billing/plan", headers=headers)
    assert res.status_code == 200
    for header in ("Deprecation", "Sunset", "Link"):
        assert header not in res.headers
    assert client.get("/api/health").status_code == 200

    # The versioned copy no longer exists, signed in or not.
    assert client.get("/api/v1/billing/plan", headers=headers).status_code == 404
    assert client.get("/api/v1/health").status_code == 404
    assert client.get("/api/v1/openapi.json").status_code == 404


def test_no_route_is_registered_twice(client):
    """Every path in the schema is either under /api/ or one of the few root pages; none is under /api/v1."""
    paths = client.get("/openapi.json").json()["paths"]
    assert not [p for p in paths if p.startswith("/api/v1")]
    assert len([p for p in paths if p.startswith("/api/")]) > 50


def test_generated_openapi_artifact():
    """Validates the OpenAPI specification written by scripts/generate_api_client.py."""
    openapi_file = BASE_DIR / "docs" / "openapi.json"
    assert openapi_file.exists(), "docs/openapi.json was not generated"

    with open(openapi_file, "r", encoding="utf-8") as f:
        spec = json.load(f)
        assert spec["info"]["version"] == "1.0.0"
        assert len(spec["paths"]) > 0
        assert all(path.startswith("/api/") and not path.startswith("/api/v1") for path in spec["paths"])


def test_adr_records_integrity():
    """Validates that all Architecture Decision Records exist and follow the standard structure."""
    adr_dir = BASE_DIR / "docs" / "adr"
    assert adr_dir.exists() and adr_dir.is_dir()

    expected_adrs = [
        "0001-dual-database-sqlite-postgres.md",
        "0002-multi-tenant-organization-isolation.md",
        "0003-browser-automation-and-stealth-posture.md",
        "0004-api-versioning-and-evolution-policy.md",
    ]

    for adr_name in expected_adrs:
        adr_path = adr_dir / adr_name
        assert adr_path.exists(), f"Missing ADR: {adr_name}"
        content = adr_path.read_text(encoding="utf-8")
        assert "## Status" in content, f"ADR {adr_name} missing Status section"
        assert "## Context" in content, f"ADR {adr_name} missing Context section"
        assert "## Decision" in content, f"ADR {adr_name} missing Decision section"
        assert "## Consequences" in content, f"ADR {adr_name} missing Consequences section"


def test_contributing_guide_integrity():
    """Validates that CONTRIBUTING.md exists and covers essential developer standards."""
    contributing_path = BASE_DIR / "CONTRIBUTING.md"
    assert contributing_path.exists(), "CONTRIBUTING.md does not exist"
    content = contributing_path.read_text(encoding="utf-8")
    assert "Quickstart & Local Environment" in content
    assert "Code Quality & Pre-Commit Hooks" in content
    assert "Architecture Invariants & Standards" in content
    assert "Testing & CI Coverage Gate" in content
    assert "--cov-fail-under=80" in content


def test_toolchain_configurations():
    """Validates that pyproject.toml and .pre-commit-config.yaml are syntactically valid."""
    pyproject_path = BASE_DIR / "pyproject.toml"
    precommit_path = BASE_DIR / ".pre-commit-config.yaml"

    assert pyproject_path.exists(), "pyproject.toml does not exist"
    assert precommit_path.exists(), ".pre-commit-config.yaml does not exist"

    # Validate pyproject.toml
    with open(pyproject_path, "rb") as f:
        pyproject_data = tomli.load(f)
        assert "tool" in pyproject_data
        assert "black" in pyproject_data["tool"]
        assert "ruff" in pyproject_data["tool"]
        assert "mypy" in pyproject_data["tool"]
        assert "pytest" in pyproject_data["tool"]
        assert "coverage" in pyproject_data["tool"]
        assert pyproject_data["tool"]["coverage"]["report"]["fail_under"] == 80

    # Validate .pre-commit-config.yaml
    with open(precommit_path, "r", encoding="utf-8") as f:
        precommit_data = yaml.safe_load(f)
        assert "repos" in precommit_data
        hook_ids = [hook["id"] for repo in precommit_data["repos"] for hook in repo.get("hooks", [])]
        assert "ruff" in hook_ids
        assert "black" in hook_ids
        assert "mypy" in hook_ids
        assert "bandit" in hook_ids
