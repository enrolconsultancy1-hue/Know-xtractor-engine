"""Tests for the opt-in logic-capture mode (bounded source-of-record)."""

from __future__ import annotations

import json

from app.analyzers.logic_capture import LogicCaptureAnalyzer
from app.analyzers.source_graph import SourceGraph
from app.domain.knowledge import LogicCaptureSection
from app.services.pipeline import AnalysisPipeline, PipelineContext
from app.services.prompt_compiler import compile_prompt

_SETTINGS_ON = {
    "enabled": True,
    "max_functions": 200,
    "max_lines_per_function": 60,
    "include_tests": False,
}


def _make_repo(tmp_path, with_secret: bool = False):
    (tmp_path / "pricing.py").write_text(
        "def calculate_price(subtotal: int, is_vip: bool) -> float:\n"
        "    base = subtotal * (0.85 if is_vip else 1.0)\n"
        "    if subtotal > 1000:\n"
        "        base -= 50\n"
        "    return round(base * 1.0825, 2)\n",
        encoding="utf-8",
    )
    (tmp_path / "helper.py").write_text(
        "def pad(s: str) -> str:\n    return s.strip()\n",
        encoding="utf-8",
    )
    (tmp_path / "main.py").write_text(
        "from fastapi import FastAPI\n"
        "from pricing import calculate_price\n"
        "app = FastAPI()\n\n"
        "@app.post('/quote')\n"
        "def quote(subtotal: int, is_vip: bool):\n"
        "    return {'total': calculate_price(subtotal, is_vip)}\n",
        encoding="utf-8",
    )
    if with_secret:
        (tmp_path / "creds.py").write_text(
            "AWS_ACCESS_KEY_ID = 'AKIAIOSFODNN7EXAMPLE'\n"
            "def load():\n"
            "    api_key = 'ghp_0123456789abcdefghijklmnopqrstuvwxyz'\n"
            "    return api_key\n",
            encoding="utf-8",
        )
    return tmp_path


def _analyze(tmp_path, settings=None):
    from app.analyzers.inventory import FileInventory

    files = FileInventory(str(tmp_path)).scan()
    ctx = {
        "logic_capture_settings": settings or _SETTINGS_ON,
        "apis": None,
        "workflows": [],
    }
    return LogicCaptureAnalyzer().analyze(str(tmp_path), files, SourceGraph(), ctx)


def test_disabled_by_default_captures_nothing(tmp_path):
    result = _analyze(tmp_path, settings={"enabled": False})
    assert result["section"] is None
    assert result["total_functions"] == 0


def test_captures_python_bodies_with_priority(tmp_path):
    _make_repo(tmp_path)
    result = _analyze(tmp_path)
    section = result["section"]
    assert section is not None
    names = [c["name"] for c in section["captured"]]
    # Endpoint handler `quote` is priority; calculate_price is workflow-relevant.
    assert "quote" in names
    assert "calculate_price" in names
    assert result["total_functions"] >= 3


def test_bodies_are_verbatim(tmp_path):
    _make_repo(tmp_path)
    result = _analyze(tmp_path)
    section = result["section"]
    body = next(c["body"] for c in section["captured"] if c["name"] == "calculate_price")
    assert "0.85" in body          # VIP multiplier survives
    assert "1.0825" in body        # tax rate survives
    assert "base -= 50" in body    # bulk discount survives


def test_bounds_skip_oversized_functions(tmp_path):
    big = ["def too_big():", "    x = 1"] + [f"    x += {i}" for i in range(80)] + ["    return x"]
    (tmp_path / "big.py").write_text("\n".join(big) + "\n", encoding="utf-8")
    result = _analyze(tmp_path)
    assert result["section"] is not None
    assert result["total_functions"] == 1
    assert result["section"]["captured"] == []       # skipped: > 60 lines
    assert result["section"]["skipped"] == 0          # not captured, but counted


def test_max_functions_budget_respected(tmp_path):
    lines = ["# module"]
    for i in range(10):
        lines += [f"def f{i}():", f"    return {i}"]
    (tmp_path / "many.py").write_text("\n".join(lines) + "\n", encoding="utf-8")
    result = _analyze(tmp_path, settings={**_SETTINGS_ON, "max_functions": 3})
    assert len(result["section"]["captured"]) == 3
    assert result["section"]["skipped"] == 7


def test_secrets_never_persist_in_captured_bodies(tmp_path):
    _make_repo(tmp_path, with_secret=True)
    result = _analyze(tmp_path)
    blob = json.dumps(result["section"])
    assert "AKIAIOSFODNN7EXAMPLE" not in blob
    assert "ghp_0123456789" not in blob
    assert "[REDACTED]" in blob


def test_end_to_end_package_and_prompt(tmp_path, monkeypatch):
    monkeypatch.setenv("KNOX_LOGIC_CAPTURE_ENABLED", "1")
    repo = _make_repo(tmp_path)
    # Reset cached settings so the env var takes effect.
    import app.core.config as cfg

    monkeypatch.setattr(cfg, "_settings", None)

    pkg = AnalysisPipeline().run(
        PipelineContext(repository="logic-demo", repo_path=str(repo))
    )
    assert pkg.logic_capture is not None
    assert pkg.logic_capture.captured
    assert any(f.category == "source-of-record" for f in pkg.facts)

    compiled = compile_prompt(pkg, max_tokens=50000)
    assert "Logic Capture" in compiled.main
    assert "re-materializes verbatim source" in compiled.main
    # Bodies land in the detail chunks.
    chunk_text = "\n".join(c.content for c in compiled.chunks) if compiled.chunks else compiled.main
    assert "0.85" in chunk_text and "1.0825" in chunk_text


def test_off_by_default_in_full_pipeline(tmp_path):
    repo = _make_repo(tmp_path)
    pkg = AnalysisPipeline().run(
        PipelineContext(repository="logic-off", repo_path=str(repo))
    )
    assert pkg.logic_capture is None


def test_section_roundtrips_through_pydantic(tmp_path):
    _make_repo(tmp_path)
    result = _analyze(tmp_path)
    section = LogicCaptureSection(**result["section"])
    assert section.captured
    assert "LOGIC CAPTURE ENABLED" in section.warning
    dumped = section.model_dump_json()
    assert "LOGIC CAPTURE ENABLED" in dumped
