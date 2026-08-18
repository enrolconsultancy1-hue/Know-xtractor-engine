"""Tests for security helpers."""

from app.core.security import classify_secret_key, is_within, sanitize_path_segment


def test_classify_secret_key():
    assert classify_secret_key("DATABASE_URL") == "connection_string"
    assert classify_secret_key("API_KEY") == "api_key"
    assert classify_secret_key("password") == "password"
    assert classify_secret_key("DEBUG") is None


def test_sanitize_path_segment():
    assert sanitize_path_segment("../../etc/passwd") == "etc_passwd"
    assert sanitize_path_segment("main") == "main"


def test_is_within(tmp_path):
    assert is_within(tmp_path, tmp_path / "sub" / "file")
    assert not is_within(tmp_path / "sub", tmp_path)
