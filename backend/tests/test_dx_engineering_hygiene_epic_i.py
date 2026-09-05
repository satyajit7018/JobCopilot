"""
Unit & Integration Tests for Phase P3 Epic I: Engineering Hygiene & Developer Experience (DX)
Validates:
1. Canonical `/api/v1/` routes and backward-compatible `/api/` routes
2. RFC 8594 `Deprecation`, `Sunset`, and `Link` response headers
3. Versioned OpenAPI specification `/api/v1/openapi.json`
4. Typed client generation (`api_client.js`, `api_client.d.ts`, `docs/openapi_v1.json`)
5. Architecture Decision Records (ADRs 0001-0004) and CONTRIBUTING.md structure
6. Configuration validation for `pyproject.toml` and `.pre-commit-config.yaml`
"""

import os
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


def test_canonical_v1_and_legacy_api_routing(client, auth_headers):
    """Validates that both /api/v1 and /api routes are functional and route to the same logic."""
    headers = {"Authorization": auth_headers["Authorization"]}

    # 1. Canonical /api/v1 route
    res_v1 = client.get("/api/v1/analytics/funnel", headers=headers)
    assert res_v1.status_code == 200
    assert "metrics" in res_v1.json()
    # Canonical v1 routes MUST NOT have Deprecation header
    assert "Deprecation" not in res_v1.headers
    assert "Sunset" not in res_v1.headers

    # 2. Legacy /api route
    res_legacy = client.get("/api/analytics/funnel", headers=headers)
    assert res_legacy.status_code == 200
    assert "metrics" in res_legacy.json()
    # Legacy routes MUST have RFC 8594 Deprecation & Sunset headers
    assert res_legacy.headers.get("Deprecation") == "true"
    assert "Sunset" in res_legacy.headers
    assert res_legacy.headers.get("Link") == '</api/v1/analytics/funnel>; rel="successor-version"'


def test_v1_openapi_schema_endpoint(client):
    """Validates that /api/v1/openapi.json produces valid OpenAPI v1 specification."""
    res = client.get("/api/v1/openapi.json")
    assert res.status_code == 200
    schema = res.json()
    assert schema["info"]["title"] == "JobCopilot API v1"
    assert schema["info"]["version"] == "1.0.0"
    assert "paths" in schema
    assert any(p.startswith("/api/v1") for p in schema["paths"].keys())


def test_generated_client_artifacts():
    """Validates that generate_api_client.py creates valid specification and client files."""
    openapi_file = BASE_DIR / "docs" / "openapi_v1.json"
    client_js = BASE_DIR / "frontend" / "js" / "api_client.js"
    client_dts = BASE_DIR / "frontend" / "js" / "api_client.d.ts"

    assert openapi_file.exists(), "docs/openapi_v1.json was not generated"
    assert client_js.exists(), "frontend/js/api_client.js was not generated"
    assert client_dts.exists(), "frontend/js/api_client.d.ts was not generated"

    # Verify openapi_v1.json content
    with open(openapi_file, "r", encoding="utf-8") as f:
        spec = json.load(f)
        assert spec["info"]["version"] == "1.0.0"
        assert len(spec["paths"]) > 0

    # Verify api_client.js content
    js_content = client_js.read_text(encoding="utf-8")
    assert "class JobCopilotClient" in js_content
    assert "/api/v1" in js_content

    # Verify api_client.d.ts content
    dts_content = client_dts.read_text(encoding="utf-8")
    assert "export declare class JobCopilotClient" in dts_content


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
