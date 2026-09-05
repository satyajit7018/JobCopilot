"""
Unit and Integration Tests for Phase P2 Epic G: Observability & CI/CD Maturity
Tests OpenTelemetry distributed tracing (W3C traceparent), span hierarchy,
Prometheus /metrics, deep /health probe, and disaster recovery simulation.
"""

import pytest
import time
from fastapi.testclient import TestClient
from app.main import app
from app.core.telemetry import telemetry, SpanContext, generate_trace_id, generate_span_id
from scripts.dr_restore_drill import run_dr_restore_drill
from scripts.migration_safety_gate import run_migration_safety_gate


@pytest.fixture
def client():
    return TestClient(app)


def test_w3c_span_context_serialization():
    """Validates W3C traceparent formatting and parsing conform to specification."""
    trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
    span_id = "00f067aa0ba902b7"
    ctx = SpanContext(trace_id=trace_id, span_id=span_id, trace_flags="01")
    header = ctx.to_traceparent()
    assert header == f"00-{trace_id}-{span_id}-01"

    parsed = SpanContext.from_traceparent(header)
    assert parsed is not None
    assert parsed.trace_id == trace_id
    assert parsed.span_id == span_id
    assert parsed.trace_flags == "01"

    # Invalid header returns None
    assert SpanContext.from_traceparent("invalid-header") is None
    assert SpanContext.from_traceparent("") is None


def test_telemetry_span_hierarchy_and_attributes():
    """Validates root span and child span context inheritance across execution layers."""
    telemetry.recorder.clear()

    # Root span: http.request
    root_span = telemetry.start_span("http.request", attributes={"http.method": "POST", "http.path": "/api/apply"})
    with root_span:
        assert telemetry.get_current_span() == root_span

        # Child span: task.apply
        child_span = telemetry.start_span("task.apply", attributes={"job_id": "job_123"})
        with child_span:
            assert telemetry.get_current_span() == child_span
            assert child_span.context.trace_id == root_span.context.trace_id
            assert child_span.parent_context.span_id == root_span.context.span_id

            # Grandchild span: llm.generate
            grandchild_span = telemetry.start_span("llm.generate", attributes={"llm.provider": "local"})
            with grandchild_span:
                assert grandchild_span.context.trace_id == root_span.context.trace_id
                assert grandchild_span.parent_context.span_id == child_span.context.span_id

    spans = telemetry.recorder.get_spans(trace_id=root_span.context.trace_id)
    assert len(spans) == 3
    span_names = [s.name for s in spans]
    assert "llm.generate" in span_names
    assert "task.apply" in span_names
    assert "http.request" in span_names


def test_http_request_tracing_middleware(client):
    """Validates that HTTP requests return W3C traceparent and X-Trace-ID headers."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert "traceparent" in resp.headers
    assert "X-Trace-ID" in resp.headers
    assert "X-Span-ID" in resp.headers

    traceparent = resp.headers["traceparent"]
    parsed_ctx = SpanContext.from_traceparent(traceparent)
    assert parsed_ctx is not None
    assert parsed_ctx.trace_id == resp.headers["X-Trace-ID"]


def test_incoming_traceparent_propagation(client):
    """Validates that incoming traceparent is preserved and propagated downstream."""
    incoming_trace_id = generate_trace_id()
    incoming_span_id = generate_span_id()
    incoming_traceparent = f"00-{incoming_trace_id}-{incoming_span_id}-01"

    resp = client.get("/health", headers={"traceparent": incoming_traceparent})
    assert resp.status_code == 200
    assert resp.headers["X-Trace-ID"] == incoming_trace_id

    out_tp = resp.headers["traceparent"]
    parsed = SpanContext.from_traceparent(out_tp)
    assert parsed.trace_id == incoming_trace_id


def test_prometheus_metrics_endpoint(client):
    """Validates that /metrics exposes Prometheus metrics."""
    resp = client.get("/metrics")
    assert resp.status_code == 200
    content = resp.text
    assert "jobcopilot_http_requests_total" in content or "python_info" in content


def test_deep_health_endpoint(client):
    """Validates /health deep probe returns database and circuit status."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("healthy", "degraded")
    assert "database" in data
    assert "circuit_breakers" in data


def test_disaster_recovery_drill_execution():
    """Runs automated DR restore drill verifying cryptographic validation, RTO, and RPO."""
    report = run_dr_restore_drill()
    assert report["status"] == "SUCCESS"
    assert report["sha256_verified"] is True
    assert report["rto_sla_met"] is True
    assert report["rpo_sla_met"] is True
    assert report["total_drill_time_seconds"] < 60.0


def test_migration_safety_gate_execution():
    """Runs migration safety gate verifying upgrade to head, downgrade to base, and re-upgrade."""
    success = run_migration_safety_gate()
    assert success is True
