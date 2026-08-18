"""Tests for observability: metrics, health probes, correlation IDs, JSON logs."""

from __future__ import annotations

import json
import logging

import pytest

import app.core.config as config_module


@pytest.fixture(autouse=True)
def _clean_settings():
    yield
    config_module._settings = None


def test_healthz(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_readyz(client):
    resp = client.get("/readyz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_metrics_prometheus_format(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    body = resp.text
    assert "# TYPE http_requests_total counter" in body
    assert "http_requests_total{" in body
    assert "knox_queue_depth" in body


def test_correlation_id_echoed(client):
    resp = client.get("/healthz", headers={"X-Request-ID": "abc-123"})
    assert resp.headers.get("X-Request-ID") == "abc-123"


def test_correlation_id_generated_when_missing(client):
    resp = client.get("/healthz")
    assert resp.headers.get("X-Request-ID")


def test_json_formatter_emits_structured_fields():
    from app.core.logging import JsonFormatter

    record = logging.LogRecord("knox.test", logging.INFO, __file__, 1, "hello %s", ("world",), None)
    payload = json.loads(JsonFormatter().format(record))
    assert payload["level"] == "INFO"
    assert payload["logger"] == "knox.test"
    assert payload["message"] == "hello world"
    assert "ts" in payload


def test_setup_logging_selects_json_formatter(monkeypatch):
    monkeypatch.setenv("KNOX_LOG_FORMAT", "json")
    config_module._settings = None
    from app.core.logging import JsonFormatter, setup_logging

    root = logging.getLogger()
    old_handlers = root.handlers[:]
    old_level = root.level
    try:
        setup_logging()
        assert any(isinstance(h.formatter, JsonFormatter) for h in root.handlers)
    finally:
        root.handlers = old_handlers
        root.level = old_level
