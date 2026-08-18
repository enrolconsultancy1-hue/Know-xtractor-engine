"""Tests for production config validation and secret redaction."""

import json

from app.analyzers.config_analyzer import ConfigAnalyzer
from app.analyzers.inventory import FileInventory
from app.analyzers.source_graph import SourceGraph
from app.core.config import Settings


def test_validate_production_flags_sqlite_and_wildcard_cors():
    problems = Settings(
        environment="production",
        database_url="sqlite:///./data/x.db",
        cors_origins=["*"],
    ).validate_production()
    assert any("SQLite" in p for p in problems)
    assert any("CORS" in p for p in problems)


def test_validate_production_ok_for_postgres_allowlist():
    problems = Settings(
        environment="production",
        database_url="postgresql+psycopg://u:p@localhost/knox",
        cors_origins=["https://app.example.com"],
    ).validate_production()
    assert problems == []


def test_validate_dev_always_ok():
    problems = Settings(
        environment="development",
        database_url="sqlite:///./data/x.db",
    ).validate_production()
    assert problems == []


def test_config_analyzer_redacts_secrets(tmp_path):
    (tmp_path / ".env").write_text(
        "API_KEY=sk-123456\nDATABASE_URL=postgres://u:p@h/db\nDEBUG=true\n",
        encoding="utf-8",
    )
    files = FileInventory(str(tmp_path)).scan()
    result = ConfigAnalyzer().analyze(str(tmp_path), files, SourceGraph(), {})
    assert "API_KEY" in result["secret_required"]
    assert "DATABASE_URL" in result["secret_required"]
    assert result["keys"].get("DEBUG") == "<set>"
    # Raw secret values must never be persisted anywhere in the output.
    serialized = json.dumps(result)
    assert "sk-123456" not in serialized
    assert "u:p@h" not in serialized
