"""Tests for security helpers."""

import pytest

from app.core.security import classify_secret_key, is_within, redact_secrets, sanitize_path_segment


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


def test_redact_secrets_scrubs_key_value_pairs():
    text = (
        "api_key=sk-abc123\n"
        "password: hunter2\n"
        "DATABASE_URL=postgres://u:p@h/db\n"
        "debug=true\n"
    )
    out = redact_secrets(text)
    assert "sk-abc123" not in out
    assert "hunter2" not in out
    assert "postgres://u:p@h/db" not in out
    assert "[REDACTED]" in out
    assert "debug=true" in out


def test_inventory_skips_symlinks(tmp_path):
    import os

    from app.analyzers.inventory import FileInventory

    (tmp_path / "real.py").write_text("print('hi')\n", encoding="utf-8")
    outside = tmp_path.parent / "outside_secret.txt"
    outside.write_text("SECRET", encoding="utf-8")
    try:
        os.symlink(outside, tmp_path / "link.txt")
    except OSError:
        pytest.skip("symlinks not supported on this platform")
    entries = FileInventory(str(tmp_path)).scan()
    paths = [e.path for e in entries]
    assert "real.py" in paths
    assert "link.txt" not in paths
