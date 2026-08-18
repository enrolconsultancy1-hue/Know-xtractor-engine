"""Tests for file inventory."""

from app.analyzers.inventory import FileInventory
from app.analyzers.source_graph import FileCategory


def test_inventory_scans_and_classifies(sample_py_project):
    inv = FileInventory(str(sample_py_project)).scan()
    paths = {e.path for e in inv}
    assert "app/main.py" in paths
    assert "app/models.py" in paths
    assert "requirements.txt" in paths
    # .gitignore should be respected for __pycache__ (none present), but
    # we assert the config file is classified as config.
    req = next(e for e in inv if e.path == "requirements.txt")
    assert req.category == FileCategory.CONFIG


def test_inventory_ignores_hidden_dirs(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x = 1", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "x.js").write_text("// hi", encoding="utf-8")
    inv = FileInventory(str(tmp_path)).scan()
    paths = {e.path for e in inv}
    assert "src/a.py" in paths
    assert not any("node_modules" in p for p in paths)


def test_source_files_filter(sample_py_project):
    inv = FileInventory(str(sample_py_project)).scan()
    sources = FileInventory.source_files(inv)
    assert all(e.category == FileCategory.SOURCE for e in sources)
    assert any(e.path == "app/main.py" for e in sources)
