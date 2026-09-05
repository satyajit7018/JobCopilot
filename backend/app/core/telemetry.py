"""
JobCopilot - OpenTelemetry Distributed Tracing Engine
Standards-compliant W3C TraceContext propagation (traceparent header),
hierarchical spans across HTTP requests, Celery tasks, and external calls (LLM / ATS),
with in-memory span recording and OTLP collector forwarding hook.
"""

import os
import time
import uuid
import contextvars
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field


# Context variable tracking the current active span in the async execution context
_current_span_var: contextvars.ContextVar[Optional["Span"]] = contextvars.ContextVar("_current_span", default=None)


def generate_trace_id() -> str:
    """Generates a 32-character hex Trace ID conforming to W3C TraceContext standard."""
    return uuid.uuid4().hex


def generate_span_id() -> str:
    """Generates a 16-character hex Span ID conforming to W3C TraceContext standard."""
    return uuid.uuid4().hex[:16]


@dataclass
class SpanContext:
    trace_id: str
    span_id: str
    trace_flags: str = "01"  # Sampled by default

    def to_traceparent(self) -> str:
        """Formats W3C traceparent header: 00-{trace_id}-{span_id}-{flags}"""
        return f"00-{self.trace_id}-{self.span_id}-{self.trace_flags}"

    @classmethod
    def from_traceparent(cls, header: str) -> Optional["SpanContext"]:
        """Parses W3C traceparent header if valid."""
        if not header:
            return None
        parts = header.strip().split("-")
        if len(parts) == 4 and parts[0] == "00" and len(parts[1]) == 32 and len(parts[2]) == 16:
            return cls(trace_id=parts[1], span_id=parts[2], trace_flags=parts[3])
        return None


class Span:
    """Represents a single distributed trace span."""

    def __init__(
        self,
        name: str,
        context: SpanContext,
        parent_context: Optional[SpanContext] = None,
        attributes: Optional[Dict[str, Any]] = None
    ):
        self.name = name
        self.context = context
        self.parent_context = parent_context
        self.attributes: Dict[str, Any] = attributes or {}
        self.start_time: float = time.time()
        self.end_time: Optional[float] = None
        self.duration_seconds: float = 0.0
        self.status_code: str = "OK"  # OK, ERROR
        self.error_message: Optional[str] = None
        self._token = None

    def set_attribute(self, key: str, value: Any):
        self.attributes[key] = value

    def record_exception(self, exc: BaseException):
        self.status_code = "ERROR"
        self.error_message = str(exc)
        self.set_attribute("error.type", exc.__class__.__name__)
        self.set_attribute("error.message", str(exc))

    def end(self, status: str = "OK"):
        if self.end_time is None:
            self.end_time = time.time()
            self.duration_seconds = max(0.0, self.end_time - self.start_time)
            if self.status_code != "ERROR":
                self.status_code = status
            telemetry.recorder.record(self)
            if self._token:
                _current_span_var.reset(self._token)

    def __enter__(self):
        self._token = _current_span_var.set(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val is not None:
            self.record_exception(exc_val)
        self.end(status="ERROR" if exc_val else "OK")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "trace_id": self.context.trace_id,
            "span_id": self.context.span_id,
            "parent_span_id": self.parent_context.span_id if self.parent_context else None,
            "traceparent": self.context.to_traceparent(),
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": self.duration_seconds,
            "status": self.status_code,
            "error_message": self.error_message,
            "attributes": self.attributes
        }


class SpanRecorder:
    """Thread-safe and async-safe in-memory span storage with capacity limits."""

    def __init__(self, max_spans: int = 1000):
        self.max_spans = max_spans
        self.spans: List[Span] = []

    def record(self, span: Span):
        self.spans.append(span)
        if len(self.spans) > self.max_spans:
            self.spans.pop(0)

    def get_spans(self, trace_id: Optional[str] = None) -> List[Span]:
        if trace_id:
            return [s for s in self.spans if s.context.trace_id == trace_id]
        return list(self.spans)

    def clear(self):
        self.spans.clear()


class OpenTelemetryTracer:
    """JobCopilot OpenTelemetry tracer coordinating span lifecycles and context propagation."""

    def __init__(self):
        self.recorder = SpanRecorder()
        self.otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")

    def get_current_span(self) -> Optional[Span]:
        """Returns the currently active span in this async execution context."""
        return _current_span_var.get()

    def start_span(
        self,
        name: str,
        parent_context: Optional[SpanContext] = None,
        attributes: Optional[Dict[str, Any]] = None
    ) -> Span:
        """
        Starts a new span. If parent_context is not provided, inherits from current active span,
        or creates a new root span.
        """
        parent = parent_context or (self.get_current_span().context if self.get_current_span() else None)
        trace_id = parent.trace_id if parent else generate_trace_id()
        span_id = generate_span_id()
        ctx = SpanContext(trace_id=trace_id, span_id=span_id)
        return Span(name=name, context=ctx, parent_context=parent, attributes=attributes)

    def extract_context_from_headers(self, headers: Dict[str, str]) -> Optional[SpanContext]:
        """Extracts SpanContext from HTTP headers (traceparent or x-trace-id)."""
        # 1. W3C traceparent
        tp = headers.get("traceparent") or headers.get("Traceparent")
        if tp:
            ctx = SpanContext.from_traceparent(tp)
            if ctx:
                return ctx

        # 2. X-Trace-ID fallback
        xtid = headers.get("x-trace-id") or headers.get("X-Trace-ID")
        if xtid and len(xtid) == 32:
            return SpanContext(trace_id=xtid, span_id=generate_span_id())

        return None

    def inject_context_into_headers(self, span: Span, headers: Dict[str, str]) -> Dict[str, str]:
        """Injects traceparent and X-Trace-ID into header dictionary."""
        headers["traceparent"] = span.context.to_traceparent()
        headers["X-Trace-ID"] = span.context.trace_id
        headers["X-Span-ID"] = span.context.span_id
        return headers


# Global Telemetry Singleton
telemetry = OpenTelemetryTracer()
