"""AI provider implementations.

Only lightweight, optional providers are implemented. They use the standard
library (`urllib`) so KNOX has no hard dependency on any vendor SDK. Set the
KNOX_AI_PROVIDER env var to enable one; the default ("none") is fully offline.
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

from app.ai.base import AIProvider, NullProvider


class _HttpProvider(AIProvider):
    """Base for simple HTTP-chat providers."""

    endpoint: str = ""
    env_key: str = ""
    model: str = ""

    def available(self) -> bool:
        return bool(self.endpoint and os.environ.get(self.env_key))

    def complete(self, prompt: str, **kwargs: Any) -> str:
        if not self.available():
            return ""
        api_key = os.environ.get(self.env_key)
        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
        }
        req = urllib.request.Request(
            self.endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
        except Exception:
            return ""


class OpenAIProvider(_HttpProvider):
    name = "openai"
    endpoint = "https://api.openai.com/v1/chat/completions"
    env_key = "KNOX_OPENAI_API_KEY"
    model = "gpt-4o-mini"


class AnthropicProvider(_HttpProvider):
    name = "anthropic"
    endpoint = "https://api.anthropic.com/v1/messages"
    env_key = "KNOX_ANTHROPIC_API_KEY"
    model = "claude-3-5-sonnet-latest"


class GeminiProvider(_HttpProvider):
    name = "gemini"
    endpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
    env_key = "KNOX_GEMINI_API_KEY"
    model = "gemini-1.5-flash"


_PROVIDERS: dict[str, type[AIProvider]] = {
    "none": NullProvider,
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
}


def build_provider(name: str | None) -> AIProvider:
    cls = _PROVIDERS.get((name or "none").lower(), NullProvider)
    return cls()
