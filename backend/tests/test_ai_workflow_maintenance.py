"""Tests for AI providers, workflow domain, maintenance, and API endpoints."""

from __future__ import annotations

import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import app.core.config as cfg
from app.ai.base import NullProvider
from app.ai.providers import (
    AnthropicProvider,
    GeminiProvider,
    OpenAIProvider,
    build_provider,
)
from app.domain.common import Confidence
from app.domain.workflow import Workflow, WorkflowStep
from app.services.maintenance import cleanup_stale_workspaces

# ── AI Providers ──────────────────────────────────────────────────────────────

def test_null_provider_available():
    assert NullProvider().available() is False


def test_null_provider_complete_returns_empty():
    assert NullProvider().complete("hello") == ""


def test_build_provider_none():
    p = build_provider("none")
    assert isinstance(p, NullProvider)


def test_build_provider_unknown_falls_back_to_null():
    p = build_provider("nonexistent_provider")
    assert isinstance(p, NullProvider)


def test_build_provider_openai():
    p = build_provider("openai")
    assert isinstance(p, OpenAIProvider)


def test_build_provider_anthropic():
    p = build_provider("anthropic")
    assert isinstance(p, AnthropicProvider)


def test_build_provider_gemini():
    p = build_provider("gemini")
    assert isinstance(p, GeminiProvider)


def test_http_provider_not_available_without_key(monkeypatch):
    monkeypatch.delenv("KNOX_OPENAI_API_KEY", raising=False)
    p = OpenAIProvider()
    assert p.available() is False


def test_http_provider_available_with_key(monkeypatch):
    monkeypatch.setenv("KNOX_OPENAI_API_KEY", "sk-test")
    p = OpenAIProvider()
    assert p.available() is True


def test_http_provider_complete_unavailable_returns_empty():
    p = OpenAIProvider()
    # No key set => returns ""
    assert p.complete("test") == ""


def test_http_provider_complete_handles_network_error(monkeypatch):
    monkeypatch.setenv("KNOX_OPENAI_API_KEY", "sk-test")
    p = OpenAIProvider()
    with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
        result = p.complete("hello")
    assert result == ""


def test_http_provider_complete_success(monkeypatch):
    monkeypatch.setenv("KNOX_OPENAI_API_KEY", "sk-test")
    p = OpenAIProvider()
    mock_response = MagicMock()
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)
    mock_response.read.return_value = b'{"choices":[{"message":{"content":"hello world"}}]}'
    with patch("urllib.request.urlopen", return_value=mock_response):
        result = p.complete("say hello")
    assert result == "hello world"


# ── Workflow domain ────────────────────────────────────────────────────────────

def _step(sid: str, deps: list[str] | None = None) -> WorkflowStep:
    return WorkflowStep(id=sid, name=sid, dependencies=deps or [])


def test_workflow_nodes():
    wf = Workflow(
        id="wf1", name="Test", entry_point="s1",
        confidence=Confidence(score=0.8),
        steps=[_step("s1"), _step("s2")],
    )
    nodes = wf.nodes()
    assert len(nodes) == 2
    assert {n.id for n in nodes} == {"s1", "s2"}


def test_workflow_edges_sequential():
    wf = Workflow(
        id="wf1", name="Test", entry_point="s1",
        confidence=Confidence(score=0.8),
        steps=[_step("s1"), _step("s2"), _step("s3")],
    )
    edges = wf.edges()
    assert ("s1", "s2") in edges
    assert ("s2", "s3") in edges


def test_workflow_edges_with_explicit_deps():
    wf = Workflow(
        id="wf1", name="Test", entry_point="s1",
        confidence=Confidence(score=0.8),
        steps=[_step("s1"), _step("s2", deps=["s1"]), _step("s3", deps=["s1"])],
    )
    edges = wf.edges()
    assert ("s1", "s2") in edges
    assert ("s1", "s3") in edges


def test_workflow_empty_steps():
    wf = Workflow(id="wf1", name="Empty", entry_point="x", confidence=Confidence(score=0.5))
    assert wf.nodes() == []
    assert wf.edges() == []


# ── Maintenance ───────────────────────────────────────────────────────────────

def test_cleanup_disabled_when_zero(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("KNOX_WORKSPACE_DIR", str(tmp_path))
    cfg._settings = None
    assert cleanup_stale_workspaces(0) == 0


def test_cleanup_no_dir(tmp_path: Path, monkeypatch):
    nonexistent = tmp_path / "no_workspace"
    monkeypatch.setenv("KNOX_WORKSPACE_DIR", str(nonexistent))
    cfg._settings = None
    assert cleanup_stale_workspaces(1) == 0


def test_cleanup_removes_old_dir(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("KNOX_WORKSPACE_DIR", str(tmp_path))
    cfg._settings = None

    old_dir = tmp_path / "old_project"
    old_dir.mkdir()
    # Make it old by setting mtime to 10 days ago
    old_ts = time.time() - (10 * 86400)
    os.utime(old_dir, (old_ts, old_ts))

    removed = cleanup_stale_workspaces(1)
    assert removed == 1
    assert not old_dir.exists()


def test_cleanup_keeps_fresh_dir(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("KNOX_WORKSPACE_DIR", str(tmp_path))
    cfg._settings = None

    fresh_dir = tmp_path / "fresh_project"
    fresh_dir.mkdir()

    removed = cleanup_stale_workspaces(7)
    assert removed == 0
    assert fresh_dir.exists()

