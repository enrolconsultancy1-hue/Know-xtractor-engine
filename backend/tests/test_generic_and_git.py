"""Tests for the generic analyzer (Kotlin, Dart) and git history — was 32% / 58%."""

from __future__ import annotations

from pathlib import Path

from app.analyzers.generic import GenericAnalyzer
from app.analyzers.source_graph import FileEntry, SourceGraph
from app.git.history import GitHistory

# ── Generic Analyzer ──────────────────────────────────────────────────────────

def test_generic_kotlin_functions(tmp_path: Path):
    src = tmp_path / "main.kt"
    src.write_text(
        "import com.example.Foo\n"
        "class MyService {\n"
        "    fun doWork(x: Int) { }\n"
        "    fun helper() { }\n"
        "}\n",
        encoding="utf-8",
    )
    files = [FileEntry(path="main.kt", language="kotlin")]
    graph = GenericAnalyzer().analyze(str(tmp_path), files, SourceGraph(), {})
    mod = graph.modules.get("main.kt")
    assert mod is not None
    names = {s.name for s in mod.symbols}
    assert "doWork" in names
    assert "helper" in names
    assert "MyService" in names


def test_generic_dart_class(tmp_path: Path):
    src = tmp_path / "widget.dart"
    src.write_text(
        "import 'package:flutter/material.dart';\n"
        "class MyWidget extends StatelessWidget {\n"
        "  Widget build(BuildContext ctx) { return Container(); }\n"
        "}\n",
        encoding="utf-8",
    )
    files = [FileEntry(path="widget.dart", language="dart")]
    graph = GenericAnalyzer().analyze(str(tmp_path), files, SourceGraph(), {})
    mod = graph.modules.get("widget.dart")
    assert mod is not None
    assert any(s.name == "MyWidget" for s in mod.symbols)


def test_generic_skips_binary():
    # binary file entry should be silently skipped
    files = [FileEntry(path="image.kt", language="kotlin", is_binary=True)]
    graph = GenericAnalyzer().analyze("/nonexistent", files, SourceGraph(), {})
    assert "image.kt" not in graph.modules


def test_generic_applicable_with_kotlin():
    assert GenericAnalyzer().applicable([FileEntry(path="a.kt", language="kotlin")])


def test_generic_not_applicable_without_supported_lang():
    assert not GenericAnalyzer().applicable([FileEntry(path="a.py", language="python")])


def test_generic_handles_read_error(tmp_path: Path):
    # file listed but does not exist on disk -> OSError captured gracefully
    files = [FileEntry(path="missing.kt", language="kotlin")]
    graph = GenericAnalyzer().analyze(str(tmp_path), files, SourceGraph(), {})
    mod = graph.modules.get("missing.kt")
    assert mod is not None
    assert any("read error" in e for e in mod.errors)


# ── Git History ────────────────────────────────────────────────────────────────

def test_git_history_no_repo(tmp_path: Path):
    gh = GitHistory(tmp_path)
    assert gh.commits() == []
    assert gh.branches() == []
    assert gh.tags() == []
    assert gh.files_changed("abc123") == []


def test_git_history_commits(git_project: Path):
    gh = GitHistory(git_project)
    commits = gh.commits()
    assert len(commits) >= 4
    c = commits[0]
    assert c.sha
    assert c.author


def test_git_history_branches(git_project: Path):
    gh = GitHistory(git_project)
    branches = gh.branches()
    assert any("main" in b or "master" in b for b in branches)


def test_git_history_tags(git_project: Path):
    gh = GitHistory(git_project)
    # No tags in the fixture, but should return an empty list not raise
    tags = gh.tags()
    assert isinstance(tags, list)


def test_git_files_changed(git_project: Path):
    gh = GitHistory(git_project)
    commits = gh.commits()
    assert commits
    files = gh.files_changed(commits[-1].sha)  # oldest commit
    assert isinstance(files, list)
