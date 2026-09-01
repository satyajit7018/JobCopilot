"""
JobCopilot - Android PWA & Mobile Static Architecture Tests
Validates Web App Manifest compliance, Service Worker root scoping,
Android icon asset integrity, and CSP headers.
"""

import json
import pytest
from fastapi.testclient import TestClient


def test_pwa_manifest_endpoint(client: TestClient):
    """Validates /manifest.json returns valid PWA config for Android installation."""
    res = client.get("/manifest.json")
    assert res.status_code == 200
    assert "application/manifest+json" in res.headers.get("content-type", "")

    data = res.json()
    assert data["name"] == "JobCopilot — Universal Autonomous Job Hunting OS"
    assert data["short_name"] == "JobCopilot"
    assert data["display"] == "standalone"
    assert data["start_url"] == "/?source=pwa"
    assert data["theme_color"] == "#6366f1"
    assert data["background_color"] == "#06080d"

    # Verify icons exist and have required Android sizes
    icons = data.get("icons", [])
    assert len(icons) >= 4
    sizes = [ic.get("sizes") for ic in icons]
    assert "192x192" in sizes
    assert "512x512" in sizes

    purposes = [ic.get("purpose") for ic in icons]
    assert "maskable" in purposes
    assert "any" in purposes


def test_service_worker_endpoint(client: TestClient):
    """Validates /sw.js returns Service Worker script with root scope permission."""
    res = client.get("/sw.js")
    assert res.status_code == 200
    assert "javascript" in res.headers.get("content-type", "")
    assert res.headers.get("service-worker-allowed") == "/"
    assert "CACHE_NAME" in res.text
    assert "STATIC_ASSETS" in res.text


def test_android_icons_static_assets(client: TestClient):
    """Validates Android app launcher icons are accessible and binary valid."""
    for icon_name in ["icon-192.png", "icon-192-maskable.png", "icon-512.png", "icon-512-maskable.png"]:
        res = client.get(f"/icons/{icon_name}")
        assert res.status_code == 200
        assert "image/png" in res.headers.get("content-type", "")
        assert len(res.content) > 100

    svg_res = client.get("/icons/icon.svg")
    assert svg_res.status_code == 200
    assert "<svg" in svg_res.text


def test_csp_pwa_security_headers(client: TestClient):
    """Validates CSP headers permit PWA manifest and worker execution."""
    res = client.get("/")
    assert res.status_code == 200
    csp = res.headers.get("content-security-policy", "")
    assert "manifest-src 'self'" in csp
    assert "worker-src 'self'" in csp
    assert "microphone=(self)" in res.headers.get("permissions-policy", "")
