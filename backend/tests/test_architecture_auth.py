"""Tests for architecture endpoint auth enforcement."""

from __future__ import annotations

import pytest

import app.core.config as config_module

_SECRET = "knx" + "-arch-" + "token"


def _auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer " + _SECRET}


def _reset_settings() -> None:
    config_module._settings = None


@pytest.fixture(autouse=True)
def _clean_settings():
    yield
    config_module._settings = None


def test_customize_requires_auth(monkeypatch, make_client):
    """POST /projects/{id}/architecture/customize must return 401 with no key."""
    monkeypatch.setenv("KNOX_AUTH_MODE", "token")
    monkeypatch.setenv("KNOX_API_KEY", _SECRET)
    _reset_settings()
    client = make_client()
    resp = client.post(
        "/api/projects/999/architecture/customize",
        json={"style": "hexagonal"},
    )
    assert resp.status_code == 401


def test_implementation_prompt_requires_auth(monkeypatch, make_client):
    """POST /projects/{id}/implementation-prompt must return 401 with no key."""
    monkeypatch.setenv("KNOX_AUTH_MODE", "token")
    monkeypatch.setenv("KNOX_API_KEY", _SECRET)
    _reset_settings()
    client = make_client()
    resp = client.post(
        "/api/projects/999/implementation-prompt",
    )
    assert resp.status_code == 401


def test_customize_open_in_none_mode(monkeypatch, make_client):
    """POST /projects/{id}/architecture/customize returns 404/409 (no pkg) in none mode."""
    monkeypatch.setenv("KNOX_AUTH_MODE", "none")
    _reset_settings()
    client = make_client()
    resp = client.post(
        "/api/projects/999/architecture/customize",
        json={"style": "hexagonal"},
    )
    # 404 because project 999 does not exist; confirms auth did not block it.
    assert resp.status_code == 404
