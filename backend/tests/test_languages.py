"""Tests for language & technology detection."""

from app.analyzers.inventory import FileInventory
from app.analyzers.languages import LanguageDetector
from app.analyzers.source_graph import SourceGraph


def test_detects_python_and_fastapi(sample_py_project):
    files = FileInventory(str(sample_py_project)).scan()
    stack = LanguageDetector().analyze(str(sample_py_project), files, SourceGraph(), {})
    langs = {t.name for t in stack.languages}
    fws = {t.name for t in stack.frameworks}
    assert "Python" in langs
    assert "FastAPI" in fws


def test_detects_sqlalchemy(sample_py_project):
    files = FileInventory(str(sample_py_project)).scan()
    stack = LanguageDetector().analyze(str(sample_py_project), files, SourceGraph(), {})
    fws = {t.name for t in stack.frameworks}
    assert "SQLAlchemy" in fws
