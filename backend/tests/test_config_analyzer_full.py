"""Comprehensive tests for ConfigAnalyzer."""

from __future__ import annotations

from pathlib import Path

from app.analyzers.config_analyzer import ConfigAnalyzer
from app.analyzers.source_graph import FileEntry, SourceGraph


def test_config_analyzer_applicable():
    analyzer = ConfigAnalyzer()
    assert analyzer.applicable([FileEntry(path="Dockerfile", language="dockerfile", size=50)])
    assert analyzer.applicable([FileEntry(path=".env", language="text", size=50)])
    assert analyzer.applicable([FileEntry(path="docker-compose.yml", language="yaml", size=50)])
    assert analyzer.applicable([FileEntry(path="config.toml", language="toml", size=50)])
    assert not analyzer.applicable([FileEntry(path="main.py", language="python", size=50)])


def test_config_analyzer_all_formats(tmp_path: Path):
    # Dockerfile
    (tmp_path / "Dockerfile").write_text("FROM python:3.11-slim\nEXPOSE 8000 8080\n", encoding="utf-8")

    # .env with both normal keys and classified secrets
    env_content = """
# App Config
APP_NAME=KnowXtractor
PORT=8000
DEBUG=

# Secrets
DATABASE_URL=postgresql://user:pass@localhost:5432/db
AWS_SECRET_ACCESS_KEY=supersecretkey123
"""
    (tmp_path / ".env").write_text(env_content, encoding="utf-8")

    # YAML with nested dict, list, and invalid yaml
    yaml_content = """
server:
  host: 0.0.0.0
  port: 8000
tags:
  - api
  - production
api_key: secretvalue
"""
    (tmp_path / "config.yaml").write_text(yaml_content, encoding="utf-8")
    (tmp_path / "bad.yaml").write_text("server: [unclosed", encoding="utf-8")

    # JSON with nested dict, list, and invalid json
    json_content = '{"database": {"engine": "postgres"}, "roles": ["admin", "user"], "token": "val"}'
    (tmp_path / "settings.json").write_text(json_content, encoding="utf-8")
    (tmp_path / "bad.json").write_text("{unclosed json", encoding="utf-8")

    # TOML
    toml_content = """
[app]
title = "knox"
version = "1.0"
"""
    (tmp_path / "pyproject.toml").write_text(toml_content, encoding="utf-8")

    # INI
    ini_content = """
[default]
worker_threads = 4
secret_token = sensitive
; comment
# another comment
"""
    (tmp_path / "setup.cfg").write_text(ini_content, encoding="utf-8")

    # Source files referencing env vars
    (tmp_path / "app.py").write_text(
        'import os\nurl = os.environ["REDIS_URL"]\nkey = os.getenv("SECRET_KEY")\n',
        encoding="utf-8",
    )
    (tmp_path / "client.ts").write_text(
        'const p = process.env.API_PORT;\nconst s = process.env["AUTH_SECRET"];\n',
        encoding="utf-8",
    )

    files = [
        FileEntry(path="Dockerfile", language="dockerfile", size=100),
        FileEntry(path=".env", language="text", size=100),
        FileEntry(path="config.yaml", language="yaml", size=100),
        FileEntry(path="bad.yaml", language="yaml", size=100),
        FileEntry(path="settings.json", language="json", size=100),
        FileEntry(path="bad.json", language="json", size=100),
        FileEntry(path="pyproject.toml", language="toml", size=100),
        FileEntry(path="setup.cfg", language="ini", size=100),
        FileEntry(path="app.py", language="python", size=100),
        FileEntry(path="client.ts", language="typescript", size=100),
        FileEntry(path="blob.bin", language="binary", size=10, is_binary=True),
    ]

    analyzer = ConfigAnalyzer()
    graph = SourceGraph()
    res = analyzer.analyze(str(tmp_path), files, graph, ctx={})

    # Dockerfile assertions
    assert res["keys"]["_docker_base_images"] == ["python:3.11-slim"]
    assert "8000 8080" in res["keys"]["_docker_expose"]

    # .env assertions
    assert res["keys"]["APP_NAME"] == "<set>"
    assert res["keys"]["PORT"] == "<set>"
    assert res["keys"]["DEBUG"] == "<empty>"
    assert "DATABASE_URL" in res["secret_required"]
    assert "AWS_SECRET_ACCESS_KEY" in res["secret_required"]

    # YAML assertions
    assert "server" in res["keys"]
    assert res["keys"]["tags"] == "<list>"
    assert res["keys"]["bad.yaml"] == "<unparseable>"

    # JSON assertions
    assert "database" in res["keys"]
    assert res["keys"]["roles"] == "<list>"
    assert res["keys"]["bad.json"] == "<unparseable>"

    # TOML & INI assertions
    assert res["keys"]["title"] == "<set>"
    assert res["keys"]["worker_threads"] == "<set>"
    assert "secret_token" in res["secret_required"]

    # Env vars from code
    assert "REDIS_URL" in res["env_vars"]
    assert "SECRET_KEY" in res["env_vars"]
    assert "API_PORT" in res["env_vars"]
    assert "AUTH_SECRET" in res["env_vars"]
