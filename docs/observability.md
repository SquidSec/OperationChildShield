# Observability configuration

Logging and tracing are implemented in `backend/app/observability.py`, which
wires `configure_logging()` and `init_tracing(app)` into the app lifespan. These
are the environment variables it reads (all default to off, so a bare checkout
behaves exactly as before).

| Variable | Default | Effect |
|----------|---------|--------|
| `LOG_JSON` | `false` | Emit one JSON object per log line (`ts`, `level`, `logger`, `message`, plus `exc_info` when present). Use behind a log collector; keep `false` for local terminal output. |
| `OTEL_ENABLED` | `false` | Enable the OpenTelemetry tracing hook. Requires the OTel packages to be installed in the backend image; when they are missing the app logs a warning and continues untraced. |
| `OTEL_ENDPOINT` | `""` | OTLP/HTTP collector endpoint (for example `http://otel-collector:4318`). Ignored unless `OTEL_ENABLED=true`. |
| `CSP_REPORT_URI` | `""` | When set, a `Content-Security-Policy-Report-Only` directive (`report-uri`) is added so browsers can report violations. Empty disables reporting. |

Notes:

- Both init calls are wrapped in `try/except` in `main.py`; an observability
  failure never blocks startup, so a missing collector cannot take the API down.
- No secrets belong in these values. `OTEL_ENDPOINT` is an internal collector
  address and should stay on the private network.
- Tracing is a no-op when disabled: no spans are created and no exporter thread
  is started, so there is no runtime cost on the default path.
