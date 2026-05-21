# Structured Logging

The platform uses JSON logs for service processes, HTTP probes, and Celery workers.

## Log Shape

Every log should include:

- `timestamp`: UTC ISO-8601 timestamp.
- `level`: `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`.
- `service`: emitting service name.
- `environment`: runtime environment when configured.
- `logger`, `module`, `function`, `line`: source context.
- `message`: stable event-like message.
- `correlation_id`: cross-service trace ID.
- `request_id`: per-hop request ID.

HTTP middleware also emits:

- `event`: `http.request.started`, `http.response.completed`, or `http.request.error`.
- `http_method`, `http_path`, `status_code`, `duration_ms`.
- `remote_addr` and `user_agent` where available.

## Distributed Systems Practices

- Propagate `X-Correlation-ID` across service calls and message metadata.
- Generate a new `X-Request-ID` per service hop when one is not supplied.
- Log request/response metadata, not request bodies.
- Never log credentials, tokens, cookies, or secrets. The shared formatter redacts common sensitive keys.
- Use stable event names in `message` or `event`, so dashboards and alerts do not depend on prose.
- Log expected client errors at `WARNING`, server failures at `ERROR`, and normal lifecycle events at `INFO`.
- Keep Celery task logs structured with task name, event type, queue, and correlation ID when available.
- Prefer UTC timestamps and stdout logs so containers and orchestrators can collect logs uniformly.
- Treat high-cardinality fields carefully; IDs are useful for traceability, but avoid logging large payloads.
