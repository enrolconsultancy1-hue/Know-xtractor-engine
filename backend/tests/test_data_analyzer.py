"""Tests for data model discovery."""

from app.analyzers.data_analyzer import DataAnalyzer
from app.analyzers.inventory import FileInventory
from app.analyzers.source_graph import SourceGraph


def test_extracts_sqlalchemy_models(sample_py_project):
    files = FileInventory(str(sample_py_project)).scan()
    model = DataAnalyzer().analyze(str(sample_py_project), files, SourceGraph(), {})
    names = {e.name for e in model.entities}
    assert "User" in names
    assert "Project" in names
    user = next(e for e in model.entities if e.name == "User")
    cols = {c.name for c in user.columns}
    assert "id" in cols
    assert "email" in cols
    assert any(c.primary_key for c in user.columns)


def test_extracts_relationship(sample_py_project):
    files = FileInventory(str(sample_py_project)).scan()
    model = DataAnalyzer().analyze(str(sample_py_project), files, SourceGraph(), {})
    rels = {(r.source, r.target) for r in model.relationships}
    assert ("Project", "User") in rels
