"""Tree-sitter analyzers for Go, Rust, Java, C#, Ruby, and PHP.

Extends KNOX's static-analysis surface beyond Python/JS/TS by parsing these
languages into the same SourceGraph (imports, function/class symbols, and call
sites). Call sites feed the call-graph / data-flow layer; imports feed
dependency and integration analysis. No repository code is ever executed.

Degrades gracefully: if tree-sitter is unavailable, ``applicable()`` returns
False and the pipeline's heuristic analyzers remain the only path.
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

    _AVAILABLE = True
except Exception:  # noqa: BLE001 — optional dependency
    _AVAILABLE = False

# language -> tree-sitter grammar config. Node types are verified against the
# installed tree-sitter-language-pack grammars.
_LANG_CONFIG: dict[str, dict] = {
    "go": {
        "grammar": "go",
        "functions": ("function_declaration", "method_declaration"),
        "classes": ("type_spec",),
        "imports": ("import_declaration",),
        "calls": ("call_expression",),
    },
    "rust": {
        "grammar": "rust",
        "functions": ("function_item",),
        "classes": ("struct_item", "enum_item", "trait_item", "impl_item"),
        "imports": ("use_declaration",),
        "calls": ("call_expression", "macro_invocation"),
    },
    "java": {
        "grammar": "java",
        "functions": ("method_declaration", "constructor_declaration"),
        "classes": ("class_declaration", "interface_declaration", "enum_declaration", "record_declaration"),
        "imports": ("import_declaration",),
        "calls": ("method_invocation", "object_creation_expression"),
    },
    "csharp": {
        "grammar": "csharp",
        "functions": ("method_declaration", "constructor_declaration", "local_function_statement"),
        "classes": ("class_declaration", "interface_declaration", "struct_declaration", "enum_declaration", "record_declaration"),
        "imports": ("using_directive",),
        "calls": ("invocation_expression", "object_creation_expression"),
    },
    "ruby": {
        "grammar": "ruby",
        "functions": ("method", "singleton_method"),
        "classes": ("class", "module"),
        "imports": (),  # handled via require/require_relative calls
        "calls": ("call", "command"),
    },
    "php": {
        "grammar": "php",
        "functions": ("function_definition", "method_declaration"),
        "classes": ("class_declaration", "interface_declaration", "trait_declaration", "enum_declaration"),
        "imports": ("namespace_use_declaration",),
        "calls": ("function_call_expression", "member_call_expression", "scoped_call_expression", "object_creation_expression"),
    },
}

_GO_STRING_LITERALS = ("interpreted_string_literal", "raw_string_literal", "string_literal")


def _text(node, source: str) -> str:
    return source[node.start_byte:node.end_byte]


def _unquote(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] in "\"'`" and s[-1] == s[0]:
        return s[1:-1]
    return s


def _decl_name(node, source: str) -> str:
    n = node.child_by_field_name("name")
    if n is not None:
        return _text(n, source)
    return ""


def _callee_text(node, source: str) -> str:
    """Extract a paren-free call target, e.g. ``session.save`` / ``db.Query``."""
    fn = node.child_by_field_name("function")
    if fn is not None:
        return _text(fn, source)
    macro = node.child_by_field_name("macro")
    if macro is not None:
        return _text(macro, source)
    name = node.child_by_field_name("name")
    if name is not None:
        prefix = ""
        for field in ("object", "receiver", "scope"):
            r = node.child_by_field_name(field)
            if r is not None:
                prefix = _text(r, source) + "."
                break
        return prefix + _text(name, source)
    typ = node.child_by_field_name("type")
    if typ is not None:
        return _text(typ, source)
    method = node.child_by_field_name("method")
    if method is not None:
        prefix = ""
        r = node.child_by_field_name("receiver")
        if r is not None:
            prefix = _text(r, source) + "."
        return prefix + _text(method, source)
    msg = node.child_by_field_name("message")
    if msg is not None:
        return _text(msg, source)
    # Fallback: first named child (e.g. PHP `new Foo()` -> "Foo").
    for child in node.named_children:
        return _text(child, source)
    return ""


def _find_nodes(node, types: tuple[str, ...]):
    out: list = []
    if node.type in types:
        out.append(node)
    for child in node.children:
        out.extend(_find_nodes(child, types))
    return out


def _clean_import(text: str, keyword: str, tail: str) -> str:
    t = text.strip()
    if t.startswith(keyword):
        t = t[len(keyword):]
    if t.endswith(tail):
        t = t[:-len(tail)]
    return t.strip()


def _import_text(node, language: str, source: str) -> list[str]:
    if language == "go":
        return [_unquote(_text(n, source)) for n in _find_nodes(node, _GO_STRING_LITERALS)]
    if language == "rust":
        return [_clean_import(_text(node, source), "use", ";")]
    if language == "java":
        return [_clean_import(_text(node, source), "import", ";")]
    if language == "csharp":
        return [_clean_import(_text(node, source), "using", ";")]
    if language == "php":
        return [_clean_import(_text(node, source), "use", ";")]
    return []


class TreeSitterGeneralAnalyzer(BaseAnalyzer):
    """Parses Go/Rust/Java/C#/Ruby/PHP into the source graph."""

    name = "treesitter_general"

    def applicable(self, files: list[FileEntry]) -> bool:
        if not _AVAILABLE:
            return False
        return any(f.language in _LANG_CONFIG for f in files)

    def analyze(self, root: str, files: list[FileEntry], graph: SourceGraph, ctx: dict) -> SourceGraph:
        root_path = Path(root)
        for f in files:
            if f.language not in _LANG_CONFIG or f.is_binary:
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
        cfg = _LANG_CONFIG[language]
        try:
            parser = get_parser(cfg["grammar"])  # type: ignore[arg-type]
            tree = parser.parse(source.encode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            module.errors.append(f"tree-sitter error: {exc}")
            return module
        self._walk(tree.root_node, source, module, language, cfg)
        return module

    def _walk(self, node, source: str, module: SourceModule, language: str, cfg: dict) -> None:
        t = node.type

        # Ruby require/require_relative -> import.
        if language == "ruby" and t == "call":
            m = node.child_by_field_name("method")
            if m is not None and _text(m, source) in ("require", "require_relative"):
                args = node.child_by_field_name("arguments")
                if args is not None:
                    for lit in _find_nodes(args, ("string",)):
                        self._add_import(module, _unquote(_text(lit, source)))

        if t in cfg["imports"]:
            for p in _import_text(node, language, source):
                self._add_import(module, p)

        if t in cfg["calls"]:
            callee = _callee_text(node, source)
            if callee:
                module.calls.append(callee)

        if t in cfg["functions"]:
            module.symbols.append(self._symbol(node, source, module.path, SymbolKind.FUNCTION, cfg))
        elif t in cfg["classes"]:
            module.symbols.append(self._symbol(node, source, module.path, SymbolKind.CLASS, cfg))

        for child in node.children:
            self._walk(child, source, module, language, cfg)

    def _symbol(self, node, source: str, path: str, kind: SymbolKind, cfg: dict) -> Symbol:
        name = _decl_name(node, source) or "anonymous"
        return Symbol(
            name=name, kind=kind, path=path, line=node.start_point[0] + 1,
            calls=_collect_calls(node, source, cfg),
        )

    @staticmethod
    def _add_import(module: SourceModule, path: str) -> None:
        if path and not any(i.module == path for i in module.imports):
            module.imports.append(Import(module=path, names=[]))


def _collect_calls(node, source: str, cfg: dict) -> list[str]:
    out: list[str] = []
    call_types = cfg["calls"]

    def rec(n) -> None:
        if n.type in call_types:
            c = _callee_text(n, source)
            if c:
                out.append(c)
        for child in n.children:
            rec(child)

    for child in node.children:
        rec(child)
    return out
