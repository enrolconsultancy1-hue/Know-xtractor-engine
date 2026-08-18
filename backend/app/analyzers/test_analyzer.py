"""Test analysis: treat tests as behavioral evidence."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.analyzers.base import BaseAnalyzer
from app.analyzers.source_graph import FileEntry, SourceGraph

_TEST_FUNC_RE = re.compile(r"def\s+(test_[A-Za-z0-9_]+|it_[A-Za-z0-9_]+)\s*\(")
_ASSERT_RE = re.compile(r"\bassert\b")
_FIXTURE_RE = re.compile(r"(?:@pytest\.fixture|def\s+fixture_|@before|@beforeEach|mock|Mock)\b")


class TestAnalyzer(BaseAnalyzer):
    name = "tests"

    def applicable(self, files: list[FileEntry]) -> bool:
        return any(f.category.value == "test" or "test" in f.path.lower() for f in files)

    def analyze(self, root: str, files: list[FileEntry], graph: SourceGraph, ctx: dict) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        root_path = Path(root)
        for f in files:
            is_test = f.category.value == "test" or "test" in f.path.lower() or f.path.endswith(
                ("test.py", "test.js", "test.ts", "spec.py", "spec.js", "spec.ts", "_test.py")
            )
            if not is_test or f.is_binary:
                continue
            try:
                source = (root_path / f.path).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            funcs = _TEST_FUNC_RE.findall(source)
            asserts = len(_ASSERT_RE.findall(source))
            uses_fixtures = bool(_FIXTURE_RE.search(source))
            results.append({
                "file": f.path,
                "test_count": len(funcs),
                "test_functions": funcs[:50],
                "assertion_count": asserts,
                "uses_fixtures_or_mocks": uses_fixtures,
                "signals": self._signals(source),
            })
        return results

    @staticmethod
    def _signals(source: str) -> list[str]:
        """Extract behavioral signals from test names and structure."""
        signals: list[str] = []
        for m in re.finditer(r"def\s+(test_[A-Za-z0-9_]+)\s*\(", source):
            name = m.group(1).replace("test_", "").replace("_", " ")
            signals.append(name)
        return signals[:30]
