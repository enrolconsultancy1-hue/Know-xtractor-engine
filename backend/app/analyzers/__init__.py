"""Analyzer package: modular, registry-driven static analyzers."""

from .base import AnalyzerRegistry, registry

__all__ = ["AnalyzerRegistry", "registry"]

