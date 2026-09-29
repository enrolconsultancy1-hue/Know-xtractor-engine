"""Tests for package.json, go.mod, Cargo.toml, pyproject.toml in DependencyAnalyzer."""

from __future__ import annotations

from pathlib import Path

from app.analyzers.dependencies import DependencyAnalyzer
from app.analyzers.source_graph import FileEntry, SourceGraph


def test_package_json_parsing(tmp_path: Path):
    pkg_json = """{
  "name": "sample",
  "dependencies": {
    "react": "^18.2.0",
    "express": "^4.18.2"
  },
  "devDependencies": {
    "typescript": "^5.0.0",
    "some-unknown-util": "1.0.0"
  }
}"""
    (tmp_path / "package.json").write_text(pkg_json, encoding="utf-8")
    files = [FileEntry(path="package.json", language="json", size=len(pkg_json))]

    analyzer = DependencyAnalyzer()
    deps = analyzer.analyze(str(tmp_path), files, SourceGraph(), {})
    names = {d.name for d in deps}
    assert "react" in names
    assert "express" in names
    assert "typescript" in names
    assert "some-unknown-util" in names

    react_dep = next(d for d in deps if d.name == "react")
    assert react_dep.architectural_layer == "presentation"

    unknown_dep = next(d for d in deps if d.name == "some-unknown-util")
    assert unknown_dep.purpose == "Third-party dependency"


def test_package_json_invalid_json(tmp_path: Path):
    (tmp_path / "package.json").write_text("{invalid json", encoding="utf-8")
    files = [FileEntry(path="package.json", language="json", size=20)]
    deps = DependencyAnalyzer().analyze(str(tmp_path), files, SourceGraph(), {})
    assert deps == []


def test_go_mod_parsing(tmp_path: Path):
    go_mod = """
module github.com/example/app

go 1.22

require (
    github.com/gin-gonic/gin v1.9.1
    github.com/lib/pq v1.10.9
)
"""
    (tmp_path / "go.mod").write_text(go_mod, encoding="utf-8")
    files = [FileEntry(path="go.mod", language="go", size=len(go_mod))]

    deps = DependencyAnalyzer().analyze(str(tmp_path), files, SourceGraph(), {})
    names = {d.name for d in deps}
    assert "gin" in names
    assert "pq" in names


def test_cargo_toml_parsing(tmp_path: Path):
    cargo_toml = """
[package]
name = "knox-rs"
version = "0.1.0"

[dependencies]
tokio = "1.28"
serde = "1.0"
"""
    (tmp_path / "Cargo.toml").write_text(cargo_toml, encoding="utf-8")
    files = [FileEntry(path="Cargo.toml", language="toml", size=len(cargo_toml))]

    deps = DependencyAnalyzer().analyze(str(tmp_path), files, SourceGraph(), {})
    names = {d.name for d in deps}
    assert "tokio" in names
    assert "serde" in names


def test_pyproject_toml_parsing(tmp_path: Path):
    pyproject = """
[tool.poetry.dependencies]
fastapi = "^0.100.0"
uvicorn = "^0.22.0"
"""
    (tmp_path / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    files = [FileEntry(path="pyproject.toml", language="toml", size=len(pyproject))]

    deps = DependencyAnalyzer().analyze(str(tmp_path), files, SourceGraph(), {})
    names = {d.name for d in deps}
    assert "fastapi" in names
    assert "uvicorn" in names

