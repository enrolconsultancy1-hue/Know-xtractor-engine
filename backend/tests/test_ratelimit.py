"""Tests for API rate limiting."""

from __future__ import annotations

import pytest

import app.api.deps as deps_module
import app.core.config as config_module


@pytest.fixture(autouse=True)
def _clean():
    deps_module.default_limiter.clear()
    yield
    config_module._settings = None
    deps_module.default_limiter.clear()


def test_rate_limit_blocks_after_limit(monkeypatch, make_client):
    monkeypatch.setenv("KNOX_RATE_LIMIT_REQUESTS", "2")
    monkeypatch.setenv("KNOX_RATE_LIMIT_WINDOW_SECONDS", "60")
    config_module._settings = None
    client = make_client()
    url = "https://github.com/a/b.git"
    assert client.post("/api/projects", json={"repository_url": url}).status_code == 201
    assert client.post("/api/projects", json={"repository_url": url}).status_code == 201
    third = client.post("/api/projects", json={"repository_url": url})
    assert third.status_code == 429


def test_rate_limit_disabled_when_zero(monkeypatch, make_client):
    monkeypatch.setenv("KNOX_RATE_LIMIT_REQUESTS", "0")
    config_module._settings = None
    client = make_client()
    url = "https://github.com/a/b.git"
    for _ in range(5):
        assert client.post("/api/projects", json={"repository_url": url}).status_code == 201
