"""Web-app errors reach the server logs and Sentry, without query strings, and can't flood it."""

import logging

from fastapi.testclient import TestClient

from app.core.settings import settings
from app.main import app

client = TestClient(app)


def test_client_error_is_forwarded_without_query_string(monkeypatch, caplog):
    import sentry_sdk

    captured = []
    monkeypatch.setattr(settings, "SENTRY_DSN", "https://key@example.ingest.sentry.io/1")
    monkeypatch.setattr(sentry_sdk, "capture_message", lambda msg, level=None: captured.append(msg))
    with caplog.at_level(logging.WARNING):
        res = client.post("/api/client-errors", json={"message": "TypeError: x is undefined", "url": "/jobs?token=secret"})
    assert res.status_code == 204
    assert captured == ["[client] TypeError: x is undefined"]
    assert "secret" not in caplog.text


def test_client_errors_are_rate_limited():
    codes = [client.post("/api/client-errors", json={"message": f"e{i}"}).status_code for i in range(32)]
    assert codes.count(204) == 30 and codes[-1] == 429
