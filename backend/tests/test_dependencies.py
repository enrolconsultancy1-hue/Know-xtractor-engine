"""Tests for dependency analysis."""

from app.analyzers.dependencies import DependencyAnalyzer
from app.analyzers.inventory import FileInventory
from app.analyzers.source_graph import SourceGraph


def test_parses_requirements(sample_py_project):
    files = FileInventory(str(sample_py_project)).scan()
    deps = DependencyAnalyzer().analyze(str(sample_py_project), files, SourceGraph(), {})
    names = {d.name for d in deps}
    assert "fastapi" in names
    assert "sqlalchemy" in names
    fastapi = next(d for d in deps if d.name == "fastapi")
    assert fastapi.criticality == "critical"


def test_no_manifest_returns_empty(tmp_path):
    (tmp_path / "a.py").write_text("x=1", encoding="utf-8")
    files = FileInventory(str(tmp_path)).scan()
    deps = DependencyAnalyzer().analyze(str(tmp_path), files, SourceGraph(), {})
    assert deps == []
