"""Tree-sitter based JavaScript/TypeScript analyzer.

This replaces the regex heuristic with real syntax-tree parsing for JS/TS/TSX
(and Vue/Svelte), giving accurate import/export extraction, function/class/
method detection, React component + hook discovery, and route registration —
unaffected by comments, strings, or formatting.

It degrades gracefully: if tree-sitter is not importable, ``applicable()``
returns False and the pipeline keeps using the heuristic ``JavaScriptAnalyzer``
as a fallback (registered under ``javascript_heuristic``).
"""

from __future__ import annotations

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

try:
    from tree_sitter_language_pack import get_parser

    _TREE_SITTER_AVAILABLE = True
except Exception:  # noqa: BLE001 — optional dependency
    _TREE_SITTER_AVAILABLE = False

_GRAMMAR_BY_LANG = {
    "javascript": "javascript",
    "typescript": "typescript",
    "vue": "vue",
    "svelte": "svelte",
}

_ROUTE_METHODS = {"get", "post", "put", "patch", "delete", "use", "options", "head", "all"}


def _text(node, source: str) -> str:
    """Return the source text of a node."""
    b = node.start_byte
    e = node.end_byte
    return source[b:e]


class TreeSitterJsAnalyzer(BaseAnalyzer):
    name = "javascript"

    def applicable(self, files: list[FileEntry]) -> bool:
        if not _TREE_SITTER_AVAILABLE:
            return False
        return any(f.language in ("javascript", "typescript", "vue", "svelte") for f in files)

    def analyze(self, root: str, files: list[FileEntry], graph: SourceGraph, ctx: dict) -> SourceGraph:
        root_path = Path(root)
        for f in files:
            if f.language not in ("javascript", "typescript", "vue", "svelte") or f.is_binary:
                continue
            graph.add(self._parse_file(root_path / f.path, f.path, f.language))
        return graph

    def _parse_file(self, path: Path, rel: str, language: str) -> SourceModule:
        module = SourceModule(path=rel, language=language)
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            module.errors.append(f"read error: {exc}")
            return module
        grammar = _GRAMMAR_BY_LANG.get(language, "javascript")
        try:
            parser = get_parser(grammar)  # type: ignore[arg-type]  # dynamic but validated language key
            tree = parser.parse(source.encode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            module.errors.append(f"tree-sitter error: {exc}")
            return module
        self._walk(tree.root_node, source, module)
        return module

    # -- traversal -----------------------------------------------------

    def _walk(self, node, source: str, module: SourceModule) -> None:
        t = node.type
        if t == "import_statement":
            self._handle_import(node, source, module)
        elif t == "export_statement":
            self._handle_export(node, source, module)
        elif t in ("function_declaration", "function_expression", "method_definition"):
            self._handle_function(node, source, module)
        elif t == "class_declaration":
            self._handle_class(node, source, module)
        elif t == "call_expression":
            self._handle_call(node, source, module)
        elif t == "lexical_declaration":
            self._handle_lexical(node, source, module)

        for child in node.children:
            self._walk(child, source, module)

    # -- handlers ------------------------------------------------------

    def _handle_import(self, node, source: str, module: SourceModule) -> None:
        spec: Import | None = None
        named: list[str] = []
        for child in node.named_children:
            if child.type == "string":
                spec = Import(module=_unquote(_text(child, source)), names=[])
            elif child.type in ("import_specifier", "namespace_import", "import_clause"):
                for name in self._identifiers(child):
                    named.append(name)
        if spec is not None:
            spec.names = named
            module.imports.append(spec)

    def _handle_export(self, node, source: str, module: SourceModule) -> None:
        for child in node.named_children:
            if child.type in ("function_declaration", "class_declaration", "lexical_declaration"):
                for ident in self._identifiers(child):
                    module.symbols.append(Symbol(name=ident, kind=SymbolKind.FUNCTION, path=module.path,
                                                 line=node.start_point[0] + 1))

    def _handle_function(self, node, source: str, module: SourceModule) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        name = _text(name_node, source)
        kind = SymbolKind.COMPONENT if name[:1].isupper() else SymbolKind.FUNCTION
        module.symbols.append(Symbol(
            name=name, kind=kind, path=module.path, line=node.start_point[0] + 1,
        ))

    def _handle_class(self, node, source: str, module: SourceModule) -> None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return
        name = _text(name_node, source)
        module.symbols.append(Symbol(
            name=name, kind=SymbolKind.CLASS, path=module.path, line=node.start_point[0] + 1,
        ))

    def _handle_lexical(self, node, source: str, module: SourceModule) -> None:
        """Handle `const Foo = () => ...` (React component via arrow function)."""
        for decl in node.named_children:
            if decl.type != "variable_declarator":
                continue
            name_node = decl.child_by_field_name("name")
            value_node = decl.child_by_field_name("value")
            if name_node is None or value_node is None:
                continue
            name = _text(name_node, source)
            if value_node.type in ("arrow_function", "function_expression") and name[:1].isupper():
                module.symbols.append(Symbol(
                    name=name, kind=SymbolKind.COMPONENT, path=module.path,
                    line=node.start_point[0] + 1,
                ))

    def _handle_call(self, node, source: str, module: SourceModule) -> None:
        fn = node.child_by_field_name("function")
        if fn is None:
            return
        fn_text = _text(fn, source)
        # React hook: useX()
        if fn.type == "identifier" and fn_text.startswith("use") and fn_text[3:4].isupper():
            module.calls.append(fn_text)
            return
        # Route registration: app.get("/path", ...) / router.post("/path", ...)
        if fn.type == "member_expression":
            prop_node = fn.child_by_field_name("property")
            if prop_node is not None and _text(prop_node, source) in _ROUTE_METHODS:
                args = node.child_by_field_name("arguments")
                if args is not None:
                    for arg in args.named_children:
                        if arg.type == "string":
                            module.calls.append(f"{_text(prop_node, source)} {_unquote(_text(arg, source))}")
                            break

    # -- helpers -------------------------------------------------------

    @staticmethod
    def _identifiers(node) -> list[str]:
        """Collect identifier names under a node."""
        out: list[str] = []
        if node.type == "identifier":
            return [node.text.decode("utf-8")] if node.text else []
        if node.type == "shorthand_property_identifier_pattern":
            return [node.text.decode("utf-8")] if node.text else []
        for child in node.named_children:
            out.extend(TreeSitterJsAnalyzer._identifiers(child))
        return out


def _unquote(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] in "\"'`" and s[-1] == s[0]:
        return s[1:-1]
    return s
