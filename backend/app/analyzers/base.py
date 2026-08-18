"""Analyzer base classes and the plugin registry.

Analyzers are discovered dynamically based on repository contents, so new
language analyzers can be added as adapters without touching the pipeline.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.analyzers.source_graph import FileEntry, SourceGraph


class BaseAnalyzer(ABC):
    """Base class for all analyzers."""

    #: Lowercase analyzer name used by the registry.
    name: str = "base"

    @abstractmethod
    def applicable(self, files: list[FileEntry]) -> bool:
        """Return True if this analyzer applies to the given file inventory."""

    @abstractmethod
    def analyze(self, root: str, files: list[FileEntry], graph: SourceGraph, ctx: dict) -> Any:
        """Run the analysis and return a domain result (see registry docs)."""


class AnalyzerRegistry:
    """A registry of analyzers selected dynamically by repository contents."""

    def __init__(self) -> None:
        self._analyzers: dict[str, BaseAnalyzer] = {}

    def register(self, analyzer: BaseAnalyzer) -> None:
        self._analyzers[analyzer.name] = analyzer

    def get(self, name: str) -> BaseAnalyzer | None:
        return self._analyzers.get(name)

    def select(self, files: list[FileEntry]) -> list[BaseAnalyzer]:
        """Return analyzers that apply to the given inventory."""
        return [a for a in self._analyzers.values() if a.applicable(files)]

    def names(self) -> list[str]:
        return sorted(self._analyzers.keys())


registry = AnalyzerRegistry()
