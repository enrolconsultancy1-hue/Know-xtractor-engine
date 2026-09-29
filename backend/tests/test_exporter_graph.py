"""Tests for the knowledge graph builder and export functions."""

from __future__ import annotations

from pathlib import Path

from app.domain.knowledge import KnowledgePackage
from app.knowledge.graph import build_knowledge_graph
from app.services.exporter import export_package, to_json, to_markdown, to_yaml


def _empty_pkg() -> KnowledgePackage:
    return KnowledgePackage()


def test_to_json_roundtrip():
    pkg = _empty_pkg()
    js = to_json(pkg)
    assert '"metadata"' in js
    # Roundtrip: must deserialise without error.
    pkg2 = KnowledgePackage.model_validate_json(js)
    assert pkg2 is not None


def test_to_yaml_contains_metadata():
    pkg = _empty_pkg()
    yml = to_yaml(pkg)
    assert "metadata" in yml


def test_to_markdown_empty_pkg():
    pkg = _empty_pkg()
    md = to_markdown(pkg)
    assert "# KNOX Knowledge Package" in md


def test_knowledge_graph_empty_pkg():
    pkg = _empty_pkg()
    g = build_knowledge_graph(pkg)
    assert "nodes" in g
    assert "edges" in g
    assert "counts" in g
    assert any(n["id"] == "project" for n in g["nodes"])


def test_knowledge_graph_dedup():
    pkg = _empty_pkg()
    g = build_knowledge_graph(pkg)
    ids = [n["id"] for n in g["nodes"]]
    assert len(ids) == len(set(ids)), "Duplicate node IDs found"


def test_export_package_json(tmp_path: Path):
    pkg = _empty_pkg()
    export_package(pkg, "json", tmp_path)
    files = list(tmp_path.glob("*.json"))
    assert files, "No JSON export file created"


def test_export_package_markdown(tmp_path: Path):
    pkg = _empty_pkg()
    export_package(pkg, "markdown", tmp_path)
    files = list(tmp_path.glob("*.md"))
    assert files, "No markdown export file created"


def test_export_package_yaml(tmp_path: Path):
    pkg = _empty_pkg()
    export_package(pkg, "yaml", tmp_path)
    files = list(tmp_path.glob("*.yaml")) + list(tmp_path.glob("*.yml"))
    assert files, "No YAML export file created"
