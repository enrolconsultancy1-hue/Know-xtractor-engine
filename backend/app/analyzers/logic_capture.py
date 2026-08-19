"""Opt-in logic capture: bounded source-of-record for function bodies.

KNOX's default contract is SOURCE -> KNOWLEDGE: the package carries structure,
names, and data-flow, never verbatim logic. Some missions (byte-faithful
rebuild assistance, behavioral verification) want the bodies too. This module
implements that as an explicitly opt-in mode (``KNOX_LOGIC_CAPTURE_ENABLED=1``)
with hard bounds and mandatory secret redaction.

Guarantees:
- OFF by default; the pipeline only captures when the operator enables it.
- Bounded: at most ``max_functions`` functions, each at most
  ``max_lines_per_function`` lines; longer functions are skipped (counted).
- Prioritized: endpoint handlers and workflow participants first, then the
  rest, so the budget goes to behaviorally significant code.
- Redacted: known secret literal formats and secret-looking assignments are
  replaced with ``[REDACTED]`` before anything is persisted.

Languages: Python (exact AST spans), plus Go/Rust/Java/C#/Ruby/PHP and
JS/TS/TSX (tree-sitter spans). Other languages are not captured.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

from app.analyzers.base import BaseAnalyzer
from app.analyzers.secret_scanner import redact_known_secret_values
from app.analyzers.source_graph import FileCategory, FileEntry, SourceGraph
from app.core.security import redact_secrets

try:
    from tree_sitter_language_pack import get_parser

    _TS_AVAILABLE = True
except Exception:  # noqa: BLE001 — optional dependency
    _TS_AVAILABLE = False

# tree-sitter grammars usable for body extraction.
_TS_LANGUAGES: dict[str, str] = {
    "go": "go",
    "rust": "rust",
    "java": "java",
    "csharp": "csharp",
    "ruby": "ruby",
    "php": "php",
    "javascript": "javascript",
    "typescript": "typescript",
    "tsx": "tsx",
}

_FUNCTION_TS_NODES = {
    "function_declaration", "method_declaration", "function_item",
    "function_definition", "constructor_declaration",
}

_NAME_RE = re.compile(r"\b(?:def|func|fn|function)\s+([A-Za-z_]\w*)")

LOGIC_CAPTURE_WARNING = (
    "LOGIC CAPTURE ENABLED: this section re-materializes verbatim source "
    "of selected functions from the analyzed repository (secrets redacted). "
    "It exists only because the operator explicitly enabled "
    "KNOX_LOGIC_CAPTURE_ENABLED=1. Do not treat captured code as trusted."
)


def _redact(body: str) -> str:
    return redact_known_secret_values(redact_secrets(body))


class LogicCaptureAnalyzer(BaseAnalyzer):
    """Captures bounded, redacted function bodies when explicitly enabled."""

    name = "logic_capture"

    def applicable(self, files: list[FileEntry]) -> bool:
        return True  # participation is decided per-run by pipeline config

    def analyze(self, root: str, files: list[FileEntry], graph: SourceGraph, ctx: dict) -> dict[str, Any]:
        settings = ctx.get("logic_capture_settings") or {}
        if not settings.get("enabled"):
            return {"section": None, "skipped": 0, "total_functions": 0}

        max_functions = int(settings.get("max_functions", 200))
        max_lines = int(settings.get("max_lines_per_function", 60))
        include_tests = bool(settings.get("include_tests", False))

        # Priority names: endpoint handlers + every workflow step symbol.
        priority: set[str] = set()
        apis = ctx.get("apis")
        for ep in (apis.endpoints if apis else []):
            if ep.handler:
                priority.add(ep.handler)
        for w in ctx.get("workflows") or []:
            for s in w.steps:
                if s.name:
                    priority.add(s.name)

        root_path = Path(root)
        candidates: list[dict[str, Any]] = []
        total_functions = 0

        for f in files:
            if f.is_binary or f.category not in (FileCategory.SOURCE, FileCategory.TEST):
                continue
            if f.category == FileCategory.TEST and not include_tests:
                continue
            path = root_path / f.path
            try:
                source = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if f.language == "python":
                found, n = self._python_bodies(source, f.path, max_lines)
            elif _TS_AVAILABLE and f.language in _TS_LANGUAGES:
                found, n = self._ts_bodies(source, f.language, f.path, max_lines)
            else:
                continue
            total_functions += n
            for rec in found:
                rec["priority"] = rec["name"] in priority
                candidates.append(rec)

        # Endpoint handlers and workflow participants first (stable otherwise).
        ordered = sorted(candidates, key=lambda c: not c["priority"])
        kept = ordered[:max_functions]

        section = {
            "warning": LOGIC_CAPTURE_WARNING,
            "captured": [
                {
                    "name": c["name"], "kind": c["kind"], "path": c["path"],
                    "language": c["language"], "line": c["line"],
                    "body": _redact(c["body"]),
                }
                for c in kept
            ],
            "skipped": len(candidates) - len(kept),
            "total_functions": total_functions,
        }
        return {
            "section": section,
            "skipped": section["skipped"],
            "total_functions": total_functions,
        }

    def _python_bodies(
        self, source: str, rel: str, max_lines: int
    ) -> tuple[list[dict[str, Any]], int]:
        """Extract Python function/method bodies using exact AST line spans."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return [], 0
        lines = source.splitlines()
        out: list[dict[str, Any]] = []
        total = 0

        def visit(node: ast.AST, in_class: bool) -> None:
            nonlocal total
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.ClassDef):
                    visit(child, in_class=True)
                elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    total += 1
                    span = child.end_lineno - child.lineno + 1  # type: ignore[attr-defined]
                    if span <= max_lines:
                        body_text = "\n".join(lines[child.lineno - 1: child.end_lineno])  # type: ignore[attr-defined]
                        out.append({
                            "name": child.name,
                            "kind": "method" if in_class else "function",
                            "path": rel,
                            "language": "python",
                            "line": child.lineno,  # type: ignore[attr-defined]
                            "body": body_text,
                        })
                    visit(child, in_class=False)  # nested defs still counted

        visit(tree, in_class=False)
        return out, total

    def _ts_bodies(
        self, source: str, language: str, rel: str, max_lines: int
    ) -> tuple[list[dict[str, Any]], int]:
        """Extract function bodies via tree-sitter node byte spans."""
        try:
            parser = get_parser(_TS_LANGUAGES[language])
            tree = parser.parse(source.encode("utf-8"))
        except Exception:  # noqa: BLE001 — grammar or parse failure
            return [], 0
        out: list[dict[str, Any]] = []
        total = 0

        def walk(node) -> None:  # type: ignore[no-untyped-def]
            nonlocal total
            if node.type in _FUNCTION_TS_NODES:
                total += 1
                name_node = node.child_by_field_name("name")
                name = (
                    source[name_node.start_byte:name_node.end_byte]
                    if name_node is not None
                    else ""
                )
                if not name:
                    decl = source[node.start_byte:node.end_byte]
                    m = _NAME_RE.search(decl)
                    name = m.group(1) if m else "<anonymous>"
                span = node.end_point[0] - node.start_point[0] + 1
                if span <= max_lines:
                    out.append({
                        "name": name,
                        "kind": (
                            "method" if node.type == "method_declaration" else "function"
                        ),
                        "path": rel,
                        "language": language,
                        "line": node.start_point[0] + 1,
                        "body": source[node.start_byte:node.end_byte],
                    })
            for child in node.children:
                walk(child)

        walk(tree.root_node)
        return out, total
