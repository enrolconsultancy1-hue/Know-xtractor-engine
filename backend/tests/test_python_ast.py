"""Tests for the Python AST analyzer."""

from app.analyzers.inventory import FileInventory
from app.analyzers.python import PythonAnalyzer
from app.analyzers.source_graph import SourceGraph, SymbolKind


def test_parses_classes_and_functions(sample_py_project):
    files = FileInventory(str(sample_py_project)).scan()
    graph = SourceGraph()
    PythonAnalyzer().analyze(str(sample_py_project), files, graph, {})
    symbols = graph.all_symbols()
    names = {s.name for s in symbols}
    assert "User" in names
    assert "Project" in names
    assert "list_users" in names
    assert "create_user" in names
    # User should be classified as a model (Base declarative).
    user = next(s for s in symbols if s.name == "User")
    assert user.kind == SymbolKind.MODEL


def test_records_imports(sample_py_project):
    files = FileInventory(str(sample_py_project)).scan()
    graph = SourceGraph()
    PythonAnalyzer().analyze(str(sample_py_project), files, graph, {})
    imports = {i.module for m in graph.modules.values() for i in m.imports}
    assert "fastapi" in imports
    assert "sqlalchemy" in imports


def test_syntax_error_is_isolated(tmp_path):
    (tmp_path / "bad.py").write_text("def broken(:\n", encoding="utf-8")
    files = FileInventory(str(tmp_path)).scan()
    graph = SourceGraph()
    PythonAnalyzer().analyze(str(tmp_path), files, graph, {})
    assert "bad.py" in graph.modules
    assert graph.modules["bad.py"].errors
