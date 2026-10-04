#!/usr/bin/env python3
"""
JobCopilot - OpenAPI Specification Generator
Inspects the FastAPI application schema and writes the versioned OpenAPI
specification (`docs/openapi_v1.json`). The JavaScript client it used to emit
served only the legacy UI and was removed with it.
"""

import json
import sys
from pathlib import Path

# Add backend directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))
sys.path.insert(0, str(BASE_DIR))

from app.main import app  # noqa: E402


def generate_openapi_artifacts():
    print("🚀 Generating JobCopilot v1 OpenAPI specification...")

    # 1. Extract OpenAPI schema
    schema = app.openapi()
    v1_schema = dict(schema)
    v1_schema["info"] = {
        "title": "JobCopilot API v1",
        "version": "1.0.0",
        "description": "Version 1 of the JobCopilot Autonomous Career Operating System REST API."
    }

    # Filter paths for /api/v1
    v1_paths = {}
    for path, methods in schema.get("paths", {}).items():
        if path.startswith("/api/v1"):
            v1_paths[path] = methods

    v1_schema["paths"] = v1_paths

    # 2. Write docs/openapi_v1.json
    docs_dir = BASE_DIR / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    openapi_file = docs_dir / "openapi_v1.json"
    with open(openapi_file, "w", encoding="utf-8") as f:
        json.dump(v1_schema, f, indent=2)
    print(f"  ✓ Written: {openapi_file} ({len(v1_paths)} versioned endpoints)")

    print("✨ OpenAPI specification generated.")


if __name__ == "__main__":
    generate_openapi_artifacts()
