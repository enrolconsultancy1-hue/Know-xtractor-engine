"""Python source analyzer using the `ast` module (deterministic static analysis)."""

from __future__ import annotations

import ast
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

_ROUTE_DECORATORS = {
    "get", "post", "put", "patch", "delete", "options", "head", "route",
    "websocket", "api_route",
}

_MODEL_BASES = {
    "BaseModel",  # pydantic
    "SQLModel",
    "Base",  # sqlalchemy declarative_base()
}


class PythonAnalyzer(BaseAnalyzer):
    """AST-based analyzer for Python source files."""

    name = "python"

    def applicable(self, files: list[FileEntry]) -> bool:
        return any(f.language == "python" for f in files)

    def analyze(self, root: str, files: list[FileEntry], graph: SourceGraph, ctx: dict) -> SourceGraph:
        root_path = Path(root)
        for f in files:
            if f.language != "python" or f.is_binary:
                continue
            module = self._parse_file(root_path / f.path, f.path)
            graph.add(module)
        return graph

    def _parse_file(self, path: Path, rel: str) -> SourceModule:
        module = SourceModule(path=rel, language="python")
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            module.errors.append(f"read error: {exc}")
            return module
        try:
            tree = ast.parse(source, filename=rel)
        except SyntaxError as exc:
            module.errors.append(f"syntax error: {exc}")
            return module

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module.imports.append(Import(
                        module=alias.name, names=[alias.name], alias=alias.asname,
                    ))
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module.imports.append(Import(
                        module=node.module,
                        names=[a.name for a in node.names],
                        alias=node.names[0].asname if node.names else None,
                    ))
            elif isinstance(node, ast.Call):
                target = self._call_name(node.func)
                if target:
                    module.calls.append(target)

        # Top-level classes and functions.
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                module.symbols.append(self._class_symbol(node, rel))
            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                module.symbols.append(self._func_symbol(node, rel, SymbolKind.FUNCTION))

        return module

    def _class_symbol(self, node: ast.ClassDef, rel: str) -> Symbol:
        bases = [self._name(b) for b in node.bases]
        methods: list[Symbol] = []
        for item in node.body:
            if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                methods.append(self._func_symbol(item, rel, SymbolKind.METHOD))
        calls = [c for m in methods for c in m.calls]
        decorators = [self._name(d) for d in node.decorator_list]
        kind = SymbolKind.CLASS
        if any(b in _MODEL_BASES for b in bases):
            kind = SymbolKind.MODEL
        return Symbol(
            name=node.name, kind=kind, path=rel, line=node.lineno,
            decorators=decorators, bases=bases,
            docstring=ast.get_docstring(node) or "",
            calls=calls,
        )

    def _func_symbol(self, node: ast.FunctionDef | ast.AsyncFunctionDef, rel: str, kind: SymbolKind) -> Symbol:
        decorators = [self._name(d) for d in node.decorator_list]
        calls: list[str] = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                t = self._call_name(child.func)
                if t:
                    calls.append(t)
        params = [a.arg for a in node.args.args]
        returns = ""
        if node.returns is not None:
            returns = self._name(node.returns)
        return Symbol(
            name=node.name, kind=kind, path=rel, line=node.lineno,
            decorators=decorators, docstring=ast.get_docstring(node) or "",
            is_async=isinstance(node, ast.AsyncFunctionDef),
            params=params, returns=returns, calls=calls,
        )

    @staticmethod
    def _name(node: ast.expr | None) -> str:
        if node is None:
            return ""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            base = PythonAnalyzer._name(node.value)
            return f"{base}.{node.attr}" if base else node.attr
        if isinstance(node, ast.Subscript):
            return PythonAnalyzer._name(node.value)
        if isinstance(node, ast.Call):
            return PythonAnalyzer._name(node.func)
        if isinstance(node, ast.Constant):
            return str(node.value)
        if isinstance(node, ast.Lambda):
            return "lambda"
        return ""

    @staticmethod
    def _call_name(func: ast.expr) -> str:
        return PythonAnalyzer._name(func)


def route_decorator(decorator: str) -> tuple[str, str] | None:
    """Return (method, path) if a decorator is an HTTP route, else None."""
    if not decorator:
        return None
    parts = decorator.split(".")
    last = parts[-1]
    if last in _ROUTE_DECORATORS:
        return (last if last != "route" else "any", "")
    return None
