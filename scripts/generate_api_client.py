#!/usr/bin/env python3
"""
JobCopilot - OpenAPI Specification Generator
Inspects the FastAPI application schema and writes the OpenAPI specification
(`docs/openapi.json`). The JavaScript client it used to emit served only the
legacy UI and was removed with it.
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
    print("🚀 Generating JobCopilot OpenAPI specification...")

    # 1. Extract OpenAPI schema
    schema = app.openapi()
    api_schema = dict(schema)
    api_schema["info"] = {
        "title": "JobCopilot API",
        "version": "1.0.0",
        "description": "The JobCopilot REST API. Every endpoint is served under /api."
    }

    # Keep the API itself; leave out health checks and the legal pages
    api_paths = {}
    for path, methods in schema.get("paths", {}).items():
        if path.startswith("/api/"):
            api_paths[path] = methods

    api_schema["paths"] = api_paths

    # 2. Write docs/openapi.json
    docs_dir = BASE_DIR / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    openapi_file = docs_dir / "openapi.json"
    with open(openapi_file, "w", encoding="utf-8") as f:
        json.dump(api_schema, f, indent=2)
        f.write("\n")
    print(f"  ✓ Written: {openapi_file} ({len(api_paths)} endpoints)")

    print("✨ OpenAPI specification generated.")


if __name__ == "__main__":
    generate_openapi_artifacts()
