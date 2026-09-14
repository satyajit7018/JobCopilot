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
async def test_metrics_expose_alert_referenced_gauges():
    """/metrics must export the gauges the Prometheus alerts query, or those alerts are dead.

    Covers jobcopilot_circuit_breaker_state (JobCopilotCircuitBreakerOpen) and
    jobcopilot_dlq_tasks_count (JobCopilotDlqBuildup), and asserts an OPEN breaker
    surfaces as state="open" == 1 exactly as the alert expression matches.
    """
    from app.core.circuit_breaker import CircuitState, ats_api_breaker

    ats_api_breaker._transition_to(CircuitState.OPEN)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            text = (await ac.get("/metrics")).text
        assert "jobcopilot_dlq_tasks_count" in text
        assert 'jobcopilot_circuit_breaker_state{circuit_name="ats_api",state="open"} 1.0' in text
        assert 'jobcopilot_circuit_breaker_state{circuit_name="ats_api",state="closed"} 0.0' in text
    finally:
        ats_api_breaker._transition_to(CircuitState.CLOSED)


@pytest.mark.asyncio
async def test_client_error_sink_accepts_reports():
    """The client-error sink accepts an uncaught-JS-error payload and returns 204."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/client-errors", json={
            "message": "TypeError: undefined is not a function",
            "source": "/js/app.js",
            "line": 123,
            "stack": "at foo (/js/app.js:123)",
        })
        assert res.status_code == 204
        # Malformed / non-JSON bodies must not 500 the sink.
        res2 = await ac.post("/api/client-errors", content=b"not json",
                             headers={"Content-Type": "application/json"})
        assert res2.status_code == 204


@pytest.mark.asyncio
async def test_request_tracing_correlation_id():
    """Asserts X-Request-ID is injected onto all responses."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/health")
        assert "x-request-id" in res.headers
        assert res.headers["x-request-id"].startswith("req_")
