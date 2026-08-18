"""AI provider base classes.

KNOX uses a hybrid strategy: deterministic static analysis wherever possible,
with AI reserved for semantic interpretation and reasoning. The provider
abstraction prevents hard-coding to a single vendor.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AIProvider(ABC):
    """Abstract interface for an AI provider."""

    name: str = "base"

    @abstractmethod
    def complete(self, prompt: str, **kwargs: Any) -> str:
        """Return a text completion for a prompt."""

    @abstractmethod
    def available(self) -> bool:
        """Return True if this provider is configured and usable."""


class NullProvider(AIProvider):
    """A no-op provider used when AI is disabled (fully deterministic mode)."""

    name = "none"

    def complete(self, prompt: str, **kwargs: Any) -> str:
        return ""

    def available(self) -> bool:
        return False
