"""Tests for shared structured logging."""

import json
import logging

from flask import Flask, jsonify

from shared.shared_logging import JSONFormatter, register_flask_request_logging


def test_json_formatter_redacts_sensitive_fields():
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="created token",
        args=(),
        exc_info=None,
    )
    record.authorization = "Bearer secret"
    record.payload = {"password": "secret", "safe": "ok"}

    payload = json.loads(JSONFormatter(service_name="svc", environment="test").format(record))

    assert payload["service"] == "svc"
    assert payload["environment"] == "test"
    assert payload["authorization"] == "[REDACTED]"
    assert payload["payload"]["password"] == "[REDACTED]"
    assert payload["payload"]["safe"] == "ok"


def test_flask_request_logging_emits_request_and_response_records(caplog):
    app = Flask(__name__)
    register_flask_request_logging(app, service_name="test_service")

    @app.route("/ping")
    def ping():
        return jsonify({"ok": True}), 200

    with caplog.at_level(logging.INFO):
        response = app.test_client().get(
            "/ping?x=1",
            headers={
                "X-Correlation-ID": "corr-1",
                "X-Request-ID": "req-1",
            },
        )

    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == "corr-1"
    assert response.headers["X-Request-ID"] == "req-1"

    events = [record.__dict__.get("event") for record in caplog.records]
    assert "http.request.started" in events
    assert "http.response.completed" in events

    response_record = next(
        record for record in caplog.records
        if record.__dict__.get("event") == "http.response.completed"
    )
    assert response_record.status_code == 200
    assert response_record.correlation_id == "corr-1"
    assert response_record.request_id == "req-1"
    assert response_record.duration_ms >= 0
