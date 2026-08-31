"""
JobCopilot - Observability, Health Check & Telemetry Test Suite
Validates deep health checks, Prometheus telemetry scraping, and correlation request headers.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_health_check_endpoint():
    """Asserts /health probe returns 200 with connected database status."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert data["database"]["status"] == "healthy"
        assert "engine" in data["database"]
        assert "version" in data


@pytest.mark.asyncio
async def test_prometheus_metrics_endpoint():
    """Asserts /metrics endpoint exposes valid Prometheus plain text metrics."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/metrics")
        assert res.status_code == 200
        assert "text/plain" in res.headers.get("content-type", "")
        text = res.text
        assert "jobcopilot_http_requests_total" in text or "python_gc_objects_collected_total" in text


@pytest.mark.asyncio
async def test_request_tracing_correlation_id():
    """Asserts X-Request-ID is injected onto all responses."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/health")
        assert "x-request-id" in res.headers
        assert res.headers["x-request-id"].startswith("req_")
