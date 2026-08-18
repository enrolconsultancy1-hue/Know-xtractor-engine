"""Internal source-graph representation shared by analyzers.

This is the intermediate *index* KNOX builds from source. It is intentionally
not the final output: the knowledge package only retains extracted concepts,
relationships, and evidence references back to these files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SymbolKind(str, Enum):
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    VARIABLE = "variable"
    INTERFACE = "interface"
    COMPONENT = "component"
    ROUTE = "route"
    MODEL = "model"


class FileCategory(str, Enum):
    SOURCE = "source"
    TEST = "test"
    CONFIG = "config"
    DOC = "doc"
    ASSET = "asset"
    GENERATED = "generated"
    BUILD = "build"
    OTHER = "other"


@dataclass
class FileEntry:
    """A single discovered file."""

    path: str  # repo-relative, POSIX separators
    category: FileCategory = FileCategory.OTHER
    language: str = ""
    size: int = 0
    is_binary: bool = False
    is_generated: bool = False


@dataclass
class Import:
    """An import statement in a source file."""

    module: str
    names: list[str] = field(default_factory=list)
    alias: str | None = None


@dataclass
class Symbol:
    """A symbol (class/function/method/route/model) discovered in a file."""

    name: str
    kind: SymbolKind
    path: str  # file path
    line: int = 0
    decorators: list[str] = field(default_factory=list)
    bases: list[str] = field(default_factory=list)
    docstring: str = ""
    is_async: bool = False
    params: list[str] = field(default_factory=list)
    returns: str = ""
    calls: list[str] = field(default_factory=list)
    annotations: list[str] = field(default_factory=list)


@dataclass
class SourceModule:
    """Parsed representation of one source file."""

    path: str
    language: str
    imports: list[Import] = field(default_factory=list)
    symbols: list[Symbol] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def module_name(self) -> str:
        return self.path.replace("/", ".").replace(".py", "")


@dataclass
class SourceGraph:
    """The aggregate source graph across all parsed files."""

    modules: dict[str, SourceModule] = field(default_factory=dict)

    def add(self, module: SourceModule) -> None:
        self.modules[module.path] = module

    def all_symbols(self) -> list[Symbol]:
        return [s for m in self.modules.values() for s in m.symbols]

    def imports_by_module(self) -> dict[str, list[str]]:
        """Map module name -> list of imported module names."""
        out: dict[str, list[str]] = {}
        for m in self.modules.values():
            out[m.path] = [i.module for i in m.imports]
        return out

    def reverse_dependencies(self) -> dict[str, list[str]]:
        """Map module name -> modules that import it."""
        rev: dict[str, list[str]] = {}
        for m in self.modules.values():
            for imp in m.imports:
                rev.setdefault(imp.module, []).append(m.path)
        return rev

    def symbols_by_kind(self, kind: SymbolKind) -> list[Symbol]:
        return [s for s in self.all_symbols() if s.kind == kind]

    def error_count(self) -> int:
        return sum(len(m.errors) for m in self.modules.values())
