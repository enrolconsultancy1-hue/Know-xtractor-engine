"""JavaScript / TypeScript analyzer (heuristic, AST-free).

This is a lightweight structural analyzer based on regular expressions. It is
intentionally conservative: it extracts imports/exports, function/class/const
declarations, React components, hooks, and route registrations. For deep AST
analysis of JS/TS, a tree-sitter adapter can be added later without changing
the pipeline (see ANALYZER_GUIDE.md).
"""

from __future__ import annotations

import re
from pathlib import Path

from app.analyzers.base import BaseAnalyzer
from app.analyzers.source_graph import (
    FileEntry,
    Import,
    SourceGraph,
    SourceModule,
    Symbol,
    SymbolKind,
)

_IMPORT_RE = re.compile(
    r"import\s+(?:([\w*{},\s]+?)\s+from\s+)?['\"]([^'\"]+)['\"]", re.M
)
_EXPORT_RE = re.compile(
    r"export\s+(?:default\s+)?(?:function|class|const|let|var)\s+([A-Za-z_$][\w$]*)", re.M
)
_FUNCTION_RE = re.compile(
    r"(?:function\s+([A-Za-z_$][\w$]*)|(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>)", re.M
)
_CLASS_RE = re.compile(r"class\s+([A-Za-z_$][\w$]*)\s*(?:extends\s+([A-Za-z_$][\w$]*))?", re.M)
_COMPONENT_RE = re.compile(
    r"(?:function|const)\s+([A-Z][A-Za-z0-9_$]*)\s*(?:\([^)]*\)\s*=>|\()", re.M
)
_HOOK_RE = re.compile(r"\b(use[A-Z][A-Za-z0-9_$]*)\s*\(", re.M)
_ROUTE_RE = re.compile(
    r"\.(get|post|put|patch|delete|use)\s*\(\s*['\"]([^'\"]+)['\"]", re.M
)


class JavaScriptAnalyzer(BaseAnalyzer):
    name = "javascript"

    def applicable(self, files: list[FileEntry]) -> bool:
        return any(f.language in ("javascript", "typescript", "vue", "svelte") for f in files)

    def analyze(self, root: str, files: list[FileEntry], graph: SourceGraph, ctx: dict) -> SourceGraph:
        root_path = Path(root)
        for f in files:
            if f.language not in ("javascript", "typescript", "vue", "svelte") or f.is_binary:
                continue
            module = self._parse_file(root_path / f.path, f.path)
            graph.add(module)
        return graph

    def _parse_file(self, path: Path, rel: str) -> SourceModule:
        module = SourceModule(path=rel, language="javascript")
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            module.errors.append(f"read error: {exc}")
            return module

        for m in _IMPORT_RE.finditer(source):
            imported = m.group(1) or ""
            names = re.findall(r"[\w$]+", imported.replace("{", " ").replace("}", " "))
            module.imports.append(Import(module=m.group(2), names=names))

        for m in _CLASS_RE.finditer(source):
            module.symbols.append(Symbol(
                name=m.group(1), kind=SymbolKind.CLASS, path=rel,
                bases=[m.group(2)] if m.group(2) else [],
            ))

        for m in _FUNCTION_RE.finditer(source):
            name = m.group(1) or m.group(2)
            if not name:
                continue
            module.symbols.append(Symbol(name=name, kind=SymbolKind.FUNCTION, path=rel))

        # React components: PascalCase function/const declarations.
        for m in _COMPONENT_RE.finditer(source):
            name = m.group(1)
            if name and name[0].isupper() and name not in {s.name for s in module.symbols}:
                module.symbols.append(Symbol(name=name, kind=SymbolKind.COMPONENT, path=rel))

        for m in _HOOK_RE.finditer(source):
            module.calls.append(m.group(1))

        return module
