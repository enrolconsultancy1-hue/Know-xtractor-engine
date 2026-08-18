"""Generic analyzer for languages without a dedicated AST adapter.

Extracts module-level structure via lightweight heuristics (imports, function
and class declarations) so the pipeline still produces useful knowledge for
Go, Rust, Java, C#, PHP, Ruby, etc., until a dedicated adapter is added.
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

_PATTERNS: dict[str, dict[str, re.Pattern]] = {
    "go": {
        "import": re.compile(r"import\s+(?:\(\s*([\s\S]*?)\)|['\"]([^'\"]+)['\"])", re.M),
        "func": re.compile(r"func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)\s*\(", re.M),
        "type": re.compile(r"type\s+([A-Za-z_]\w*)\s+(?:struct|interface)", re.M),
    },
    "rust": {
        "import": re.compile(r"use\s+([\w:{},:]+);", re.M),
        "func": re.compile(r"fn\s+([A-Za-z_]\w*)\s*\(", re.M),
        "type": re.compile(r"(?:struct|enum|trait)\s+([A-Za-z_]\w*)", re.M),
    },
    "java": {
        "import": re.compile(r"import\s+([\w.]+);", re.M),
        "func": re.compile(r"(?:public|private|protected|static|\s)+[\w<>\[\]]+\s+([A-Za-z_]\w*)\s*\([^)]*\)\s*\{", re.M),
        "type": re.compile(r"(?:class|interface|enum)\s+([A-Za-z_]\w*)", re.M),
    },
    "csharp": {
        "import": re.compile(r"using\s+([\w.]+);", re.M),
        "func": re.compile(r"(?:public|private|protected|internal|static|\s)+[\w<>\[\]]+\s+([A-Za-z_]\w*)\s*\([^)]*\)\s*\{", re.M),
        "type": re.compile(r"(?:class|interface|struct|enum)\s+([A-Za-z_]\w*)", re.M),
    },
    "php": {
        "import": re.compile(r"use\s+([\w\\]+);", re.M),
        "func": re.compile(r"function\s+([A-Za-z_]\w*)\s*\(", re.M),
        "type": re.compile(r"class\s+([A-Za-z_]\w*)", re.M),
    },
    "ruby": {
        "import": re.compile(r"require\s+['\"]([^'\"]+)['\"]", re.M),
        "func": re.compile(r"def\s+([A-Za-z_]\w*)", re.M),
        "type": re.compile(r"class\s+([A-Za-z_]\w*)", re.M),
    },
    "kotlin": {
        "import": re.compile(r"import\s+([\w.]+)", re.M),
        "func": re.compile(r"fun\s+([A-Za-z_]\w*)\s*\(", re.M),
        "type": re.compile(r"(?:class|interface|object)\s+([A-Za-z_]\w*)", re.M),
    },
    "dart": {
        "import": re.compile(r"import\s+['\"]([^'\"]+)['\"]", re.M),
        "func": re.compile(r"(?:void|[\w<>?, ]+)?\s+([A-Za-z_]\w*)\s*\([^)]*\)\s*\{", re.M),
        "type": re.compile(r"class\s+([A-Za-z_]\w*)", re.M),
    },
}


class GenericAnalyzer(BaseAnalyzer):
    name = "generic"

    _SUPPORTED = {"go", "rust", "java", "csharp", "php", "ruby", "kotlin", "dart"}

    def applicable(self, files: list[FileEntry]) -> bool:
        return any(f.language in self._SUPPORTED for f in files)

    def analyze(self, root: str, files: list[FileEntry], graph: SourceGraph, ctx: dict) -> SourceGraph:
        root_path = Path(root)
        for f in files:
            if f.language not in self._SUPPORTED or f.is_binary:
                continue
            graph.add(self._parse_file(root_path / f.path, f.path, f.language))
        return graph

    def _parse_file(self, path: Path, rel: str, lang: str) -> SourceModule:
        module = SourceModule(path=rel, language=lang)
        patterns = _PATTERNS.get(lang)
        if not patterns:
            return module
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            module.errors.append(f"read error: {exc}")
            return module

        imp = patterns["import"]
        for m in imp.finditer(source):
            block = m.group(1)
            if block:
                for name in re.findall(r'["\']([^"\']+)["\']', block):
                    module.imports.append(Import(module=name))
            elif m.group(2):
                module.imports.append(Import(module=m.group(2)))

        for m in patterns["func"].finditer(source):
            module.symbols.append(Symbol(name=m.group(1), kind=SymbolKind.FUNCTION, path=rel))

        for m in patterns["type"].finditer(source):
            module.symbols.append(Symbol(name=m.group(1), kind=SymbolKind.CLASS, path=rel))

        return module
