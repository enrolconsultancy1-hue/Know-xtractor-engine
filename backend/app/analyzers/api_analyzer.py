"""API discovery: extract HTTP endpoints from route registrations."""

from __future__ import annotations

import re
from pathlib import Path

from app.analyzers.base import BaseAnalyzer
from app.analyzers.source_graph import FileEntry, SourceGraph
from app.domain.api_model import ApiEndpoint, ApiSpec
from app.domain.common import Confidence, Evidence

# Python route decorators: @app.get("/x") / @router.post("/y")
_PY_ROUTE_RE = re.compile(
    r"@([\w.]+)\.(get|post|put|patch|delete|options|head|route|websocket|api_route)"
    r"\s*\(\s*[\"']([^\"']*)[\"']"
)
_PY_FLASK_RE = re.compile(r"@(?:app|bp|blueprint)\.route\s*\(\s*[\"']([^\"']*)[\"']")
_PY_DEF_RE = re.compile(r"(?:async\s+)?def\s+([A-Za-z_]\w*)\s*\(")

# JS/TS route registrations: app.get("/x", handler)
_JS_ROUTE_RE = re.compile(
    r"(?:app|router|route)\.(get|post|put|patch|delete|use)\s*\(\s*[\"']([^\"']+)[\"']"
)

_FRAMEWORK_HINTS = {
    "fastapi": "FastAPI",
    "flask": "Flask",
    "django": "Django",
    "express": "Express",
    "router": "Express",
}


class ApiAnalyzer(BaseAnalyzer):
    name = "api"

    def applicable(self, files: list[FileEntry]) -> bool:
        return any(f.language in ("python", "javascript", "typescript") for f in files)

    def analyze(self, root: str, files: list[FileEntry], graph: SourceGraph, ctx: dict) -> ApiSpec:
        spec = ApiSpec()
        root_path = Path(root)
        frameworks: set[str] = set()

        for f in files:
            if f.language not in ("python", "javascript", "typescript") or f.is_binary:
                continue
            try:
                source = (root_path / f.path).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            if f.language == "python":
                endpoints = self._python_routes(source, f.path)
                for method, path, handler in endpoints:
                    spec.endpoints.append(ApiEndpoint(
                        method=method, path=path, handler=handler, file=f.path,
                        framework="FastAPI" if "get" in method or method != "any" else "Flask",
                        confidence=Confidence(score=0.85, rationale="route decorator"),
                        evidence=[Evidence(file=f.path, symbol=handler, reason="route decorator")],
                    ))
                    frameworks.add(spec.endpoints[-1].framework)
            else:
                clean = re.sub(r"//.*", "", source)
                clean = re.sub(r"/\*.*?\*/", "", clean, flags=re.S)
                for m in _JS_ROUTE_RE.finditer(clean):
                    spec.endpoints.append(ApiEndpoint(
                        method=m.group(1), path=m.group(2), handler="", file=f.path,
                        framework="Express",
                        confidence=Confidence(score=0.8, rationale="route registration"),
                        evidence=[Evidence(file=f.path, reason="route registration")],
                    ))
                    frameworks.add("Express")

        spec.framework = ", ".join(sorted(frameworks)) or ""
        spec.confidence = Confidence(
            score=0.8 if spec.endpoints else 0.0,
            rationale=f"{len(spec.endpoints)} endpoint(s) extracted",
        )
        return spec

    def _python_routes(self, source: str, path: str) -> list[tuple[str, str, str]]:
        """Return (method, route, handler) tuples for Python routes."""
        out: list[tuple[str, str, str]] = []
        lines = source.splitlines()
        for i, line in enumerate(lines):
            code = line.split("#")[0]
            if not code.strip():
                continue
            m = _PY_ROUTE_RE.search(code)
            if not m:
                m = _PY_FLASK_RE.search(code)
                if m:
                    method, route = "any", m.group(1)
                else:
                    continue
            else:
                method, route = m.group(2), m.group(3)
            # Find the following function def.
            handler = ""
            for j in range(i + 1, min(i + 8, len(lines))):
                dm = _PY_DEF_RE.search(lines[j])
                if dm:
                    handler = dm.group(1)
                    break
            out.append((method, route or "/", handler))
        return out
