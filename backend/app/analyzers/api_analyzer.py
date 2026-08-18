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

# Django URLconf: path('route', view) / re_path(r'...', view) / url(...).
_DJANGO_PATH_RE = re.compile(
    r"\b(?:path|re_path|url)\s*\(\s*[\"']([^\"']*)[\"']\s*,\s*([^,)]+)"
)

# gRPC protobuf: service X { rpc M (Req) returns (Resp); }
_GRPC_SERVICE_RE = re.compile(r"\bservice\s+(\w+)\s*\{")
_GRPC_RPC_RE = re.compile(r"\brpc\s+(\w+)\s*\(")

# GraphQL SDL: type Query { field(args): Type }
_GRAPHQL_TYPE_RE = re.compile(r"\btype\s+(Query|Mutation|Subscription)\s*\{")
_GRAPHQL_FIELD_RE = re.compile(r"^\s*(\w+)\s*(?:\([^)]*\))?\s*:")

# Gin (Go): router.GET("/x", handler)
_GIN_ROUTE_RE = re.compile(
    r"\.(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS|Any)\(\s*\"([^\"]+)\""
)

# Spring (Java): @Get/Post/Put/Patch/DeleteMapping("/x") + class @RequestMapping("/base")
_SPRING_VERB_RE = re.compile(
    r"@(Get|Post|Put|Patch|Delete)Mapping\s*\(\s*(?:value\s*=\s*)?\"([^\"]+)\""
)
_SPRING_BASE_RE = re.compile(r"@RequestMapping\s*\(\s*\"([^\"]+)\"\s*\)")


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
            if f.is_binary:
                continue
            ext = f.path.rsplit(".", 1)[-1].lower() if "." in f.path else ""
            is_text_source = (
                f.language in ("python", "javascript", "typescript", "go", "java")
                or ext in ("proto", "graphql", "gql")
            )
            if not is_text_source:
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
                        framework="FastAPI" if method != "any" else "Flask",
                        confidence=Confidence(score=0.85, rationale="route decorator"),
                        evidence=[Evidence(file=f.path, symbol=handler, reason="route decorator")],
                    ))
                    frameworks.add(spec.endpoints[-1].framework)
                for method, path, handler in self._django_urlconf(source, f.path):
                    spec.endpoints.append(ApiEndpoint(
                        method=method, path=path, handler=handler, file=f.path,
                        framework="Django",
                        confidence=Confidence(score=0.75, rationale="Django URLconf"),
                        evidence=[Evidence(file=f.path, symbol=handler, reason="URL pattern")],
                    ))
                    frameworks.add("Django")
            elif ext == "proto":
                for method, path, handler in self._grpc_routes(source, f.path):
                    spec.endpoints.append(ApiEndpoint(
                        method=method, path=path, handler=handler, file=f.path,
                        framework="gRPC",
                        confidence=Confidence(score=0.85, rationale="protobuf service"),
                        evidence=[Evidence(file=f.path, symbol=handler, reason="rpc definition")],
                    ))
                    frameworks.add("gRPC")
            elif ext in ("graphql", "gql"):
                for method, path, handler in self._graphql_routes(source, f.path):
                    spec.endpoints.append(ApiEndpoint(
                        method=method, path=path, handler=handler, file=f.path,
                        framework="GraphQL",
                        confidence=Confidence(score=0.8, rationale="GraphQL schema field"),
                        evidence=[Evidence(file=f.path, symbol=handler, reason="schema field")],
                    ))
                    frameworks.add("GraphQL")
            elif f.language == "go":
                for method, path, handler in self._gin_routes(source, f.path):
                    spec.endpoints.append(ApiEndpoint(
                        method=method, path=path, handler=handler, file=f.path,
                        framework="Gin",
                        confidence=Confidence(score=0.8, rationale="Gin route registration"),
                        evidence=[Evidence(file=f.path, reason="route registration")],
                    ))
                    frameworks.add("Gin")
            elif f.language == "java":
                for method, path, handler in self._spring_routes(source, f.path):
                    spec.endpoints.append(ApiEndpoint(
                        method=method, path=path, handler=handler, file=f.path,
                        framework="Spring",
                        confidence=Confidence(score=0.7, rationale="Spring mapping annotation"),
                        evidence=[Evidence(file=f.path, reason="mapping annotation")],
                    ))
                    frameworks.add("Spring")
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
            if m and (m.group(1) == "mock" or m.group(1).endswith(".mock")):
                # unittest.mock.patch(...) is not a route registration.
                m = None
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

    def _django_urlconf(self, source: str, path: str) -> list[tuple[str, str, str]]:
        """Extract (method, path, handler) from a Django ``urls.py`` URLconf."""
        out: list[tuple[str, str, str]] = []
        for m in _DJANGO_PATH_RE.finditer(source):
            route = m.group(1)
            handler = self._django_handler(m.group(2))
            out.append(("any", route, handler))
        return out

    @staticmethod
    def _django_handler(view: str) -> str:
        v = view.strip()
        if v.startswith("include"):
            return "include"
        quoted = re.match(r"[\"']([^\"']+)[\"']", v)
        if quoted:
            return quoted.group(1)
        as_view = re.match(r"(\w+)\.as_view", v)
        if as_view:
            return as_view.group(1) + ".as_view"
        return v.rstrip("()").strip() or "view"

    def _grpc_routes(self, source: str, path: str) -> list[tuple[str, str, str]]:
        """Extract (rpc, /Service.Method, Service.Method) from a .proto file."""
        out: list[tuple[str, str, str]] = []
        service = ""
        depth = 0
        for line in source.splitlines():
            sm = _GRPC_SERVICE_RE.search(line)
            if sm:
                service = sm.group(1)
                depth = line.count("{") - line.count("}")
                continue
            if service:
                rm = _GRPC_RPC_RE.search(line)
                if rm:
                    name = rm.group(1)
                    out.append(("rpc", f"/{service}.{name}", f"{service}.{name}"))
                depth += line.count("{") - line.count("}")
                if depth <= 0:
                    service = ""
        return out

    def _graphql_routes(self, source: str, path: str) -> list[tuple[str, str, str]]:
        """Extract (query|mutation, Type.field, field) from GraphQL SDL."""
        out: list[tuple[str, str, str]] = []
        current = ""
        depth = 0
        for line in source.splitlines():
            tm = _GRAPHQL_TYPE_RE.search(line)
            if tm:
                current = tm.group(1)
                depth = line.count("{") - line.count("}")
                continue
            if current:
                if line.strip().startswith("}"):
                    depth -= 1
                    if depth <= 0:
                        current = ""
                    continue
                fm = _GRAPHQL_FIELD_RE.match(line)
                if fm:
                    out.append((current.lower(), f"{current}.{fm.group(1)}", fm.group(1)))
        return out

    def _gin_routes(self, source: str, path: str) -> list[tuple[str, str, str]]:
        """Extract (verb, path, '') from Gin route registrations."""
        out: list[tuple[str, str, str]] = []
        for m in _GIN_ROUTE_RE.finditer(source):
            verb = m.group(1).lower() if m.group(1) != "Any" else "any"
            out.append((verb, m.group(2), ""))
        return out

    def _spring_routes(self, source: str, path: str) -> list[tuple[str, str, str]]:
        """Extract (verb, path, '') from Spring mapping annotations."""
        out: list[tuple[str, str, str]] = []
        base = ""
        bm = _SPRING_BASE_RE.search(source)
        if bm:
            base = bm.group(1).rstrip("/")
        for m in _SPRING_VERB_RE.finditer(source):
            verb = m.group(1).lower()
            p = m.group(2)
            full = p if not base else (base + (p if p.startswith("/") else "/" + p))
            out.append((verb, full, ""))
        return out
