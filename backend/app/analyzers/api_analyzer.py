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
_PY_FLASK_RE = re.compile(r"@(\w+)\.route\s*\(\s*[\"']([^\"']*)[\"']")
_PY_DEF_RE = re.compile(r"(?:async\s+)?def\s+([A-Za-z_]\w*)\s*\(")
_PY_ROUTER_DEF_RE = re.compile(r"(\w+)\s*=\s*(?:APIRouter|Router|Blueprint)\s*\(([^)]*)\)")
_PY_PREFIX_ARG_RE = re.compile(r"(?:prefix|url_prefix)\s*=\s*[\"']([^\"']+)[\"']")
_PY_INCLUDE_RE = re.compile(
    r"(?:include_router|register_blueprint)\s*\(\s*([\w.]+)\s*,"
    r"[^)]*?(?:prefix|url_prefix)\s*=\s*[\"']([^\"']+)[\"']"
)

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

        router_prefix, include_prefix = self._collect_prefixes(files, root_path)
        prefix_map: dict[str, str] = {}
        for var, p in router_prefix.items():
            prefix_map[var] = include_prefix.get(var, "") + p
        for var, p in include_prefix.items():
            prefix_map.setdefault(var, p)

        for f in files:
            if f.language not in ("python", "javascript", "typescript") or f.is_binary:
                continue
            try:
                source = (root_path / f.path).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            if f.language == "python":
                endpoints = self._python_routes(source, f.path, prefix_map)
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

    def _python_routes(self, source: str, path: str, prefix_map: dict[str, str]) -> list[tuple[str, str, str]]:
        """Return (method, route, handler) tuples for Python routes.

        Router prefixes (APIRouter/Blueprint definitions and
        include_router/register_blueprint registrations) are resolved and
        prepended to each route path.
        """
        out: list[tuple[str, str, str]] = []
        lines = source.splitlines()
        for i, line in enumerate(lines):
            code = line.split("#")[0]
            if not code.strip():
                continue
            m = _PY_ROUTE_RE.search(code)
            if m:
                method, route = m.group(2), m.group(3)
                obj_name = m.group(1).split(".")[-1]
            else:
                m = _PY_FLASK_RE.search(code)
                if not m:
                    continue
                method, route = "any", m.group(2)
                obj_name = m.group(1)
            route = self._with_prefix(obj_name, route, prefix_map)
            # Find the following function def.
            handler = ""
            for j in range(i + 1, min(i + 8, len(lines))):
                dm = _PY_DEF_RE.search(lines[j])
                if dm:
                    handler = dm.group(1)
                    break
            out.append((method, route, handler))
        return out

    def _collect_prefixes(
        self, files: list[FileEntry], root_path: Path
    ) -> tuple[dict[str, str], dict[str, str]]:
        """Map router object names to their declared prefixes.

        Returns ``(router_prefix, include_prefix)``: APIRouter/Blueprint
        definitions and include_router/register_blueprint registrations, each
        keyed by the router object's last name segment.
        """
        router_prefix: dict[str, str] = {}
        include_prefix: dict[str, str] = {}
        for f in files:
            if f.language != "python" or f.is_binary:
                continue
            try:
                source = (root_path / f.path).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for m in _PY_ROUTER_DEF_RE.finditer(source):
                pm = _PY_PREFIX_ARG_RE.search(m.group(2))
                if pm:
                    router_prefix[m.group(1)] = pm.group(1)
            for m in _PY_INCLUDE_RE.finditer(source):
                include_prefix[m.group(1).split(".")[-1]] = m.group(2)
        return router_prefix, include_prefix

    @staticmethod
    def _with_prefix(obj_name: str, route: str, prefix_map: dict[str, str]) -> str:
        prefix = prefix_map.get(obj_name, "")
        route = route or "/"
        if not prefix:
            return route if route.startswith("/") else "/" + route
        full = prefix.rstrip("/") + route if route.startswith("/") else prefix.rstrip("/") + "/" + route
        return full if full.startswith("/") else "/" + full
