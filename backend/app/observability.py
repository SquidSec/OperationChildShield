"""Logging and tracing setup.

JSON logs are opt-in (LOG_JSON=1) so local development keeps readable output.
Tracing is a no-op unless OTEL_ENABLED is set *and* the OpenTelemetry packages
are installed; they are not a runtime dependency of this service.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from app.config import settings

_CONFIGURED = False

# Attributes the stdlib puts on every record; anything else came through
# ``extra=`` and is worth emitting in the JSON line.
_RESERVED_ATTRS = frozenset(
    vars(logging.LogRecord("", 0, "", 0, "", (), None)).keys()
) | {"message", "asctime", "taskName"}


class JsonFormatter(logging.Formatter):
    """One JSON object per line, with caller ``extra`` fields merged in."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in _RESERVED_ATTRS or key.startswith("_"):
                continue
            payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    """Install the JSON formatter when LOG_JSON is true. Idempotent."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    if settings.log_json:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        root = logging.getLogger()
        root.handlers = [handler]
        root.setLevel(root.level or logging.INFO)
    _CONFIGURED = True


def init_tracing(app) -> bool:
    """Attach OTLP tracing when enabled and available. Returns True on success."""
    if not settings.otel_enabled:
        return False
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        logging.getLogger(__name__).warning(
            "OTEL_ENABLED is set but the opentelemetry packages are not installed; "
            "tracing stays off"
        )
        return False

    resource = Resource.create({"service.name": "operation-child-shield-api"})
    provider = TracerProvider(resource=resource)
    exporter = (
        OTLPSpanExporter(endpoint=settings.otel_endpoint)
        if settings.otel_endpoint
        else OTLPSpanExporter()
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)
    return True


async def record_request_metrics(request, call_next):
    """Minimal request timing middleware: one log line per request."""
    import time

    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
    logging.getLogger("app.request").info(
        "request",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": elapsed_ms,
        },
    )
    return response
