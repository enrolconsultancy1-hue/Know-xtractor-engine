"""Component discovery: turn symbols + modules into architectural components."""

from __future__ import annotations

from app.analyzers.source_graph import SourceGraph, Symbol, SymbolKind
from app.domain.common import Confidence, Evidence
from app.domain.component import Component, ComponentType

_LAYER_BY_PATH: list[tuple[tuple[str, ...], str]] = [
    (("api", "controllers", "routes", "views", "endpoints", "handlers", "routers"), "presentation"),
    (("providers",), "provider"),
    (("services", "application", "usecases", "use_cases", "biz", "business"), "application"),
    (("domain", "models", "entities", "core", "schema"), "domain"),
    (("repositories", "repository", "dao", "db", "database", "infra", "persistence", "storage"), "persistence"),
    (("config", "settings", "configuration", "env"), "configuration"),
    (("tests", "test"), "testing"),
    (("middleware", "middlewares", "interceptors"), "middleware"),
    (("worker", "workers", "jobs", "tasks", "queue", "celery"), "background"),
    (("cli", "commands", "scripts"), "cli"),
    (("src", "client", "frontend", "ui"), "client"),
    (("build", "tools", "pinokio"), "tooling"),
]

_ENTRYPOINT_FILES = {
    "main.py", "app.py", "index.py", "manage.py", "run.py", "wsgi.py", "asgi.py",
    "index.js", "index.ts", "main.js", "main.ts", "server.js", "server.ts",
    "local.js",  # gods-eye-view provider registry
}

# Symbol names that are trivially named or anonymous — skip as noise
_TRIVIAL_NAMES = {"", "_", "__", "anonymous", "cb", "fn", "handler",
                   "err", "e", "res", "req", "next", "reject", "resolve"}

# Minimum name length to include a function symbol (avoids `a`, `cb`, etc.)
_MIN_SYMBOL_NAME_LEN = 3


def infer_layer(path: str) -> str:
    lower = path.lower()
    for keywords, layer in _LAYER_BY_PATH:
        if any(k in lower for k in keywords):
            return layer
    return "application"


class ComponentExtractor:
    """Builds Component objects from the source graph."""

    def __init__(self, graph: SourceGraph) -> None:
        self.graph = graph
        self.rev = graph.reverse_dependencies()

    def extract(self) -> list[Component]:
        components: list[Component] = []
        components.extend(self._module_components())
        components.extend(self._symbol_components())
        return self._link(components)

    def _module_components(self) -> list[Component]:
        out: list[Component] = []
        for path, module in self.graph.modules.items():
            name = module.module_name
            layer = infer_layer(path)
            ctype = ComponentType.MODULE
            if path.split("/")[-1] in _ENTRYPOINT_FILES:
                ctype = ComponentType.APPLICATION
                layer = "entrypoint"
            out.append(Component(
                id=f"module:{path}", name=name, type=ctype,
                purpose=self._module_purpose(path, module),
                location=path, architectural_layer=layer,
                dependencies=[i.module for i in module.imports],
                confidence=Confidence(score=0.9, rationale="source module"),
                evidence=[Evidence(file=path, reason="source file")],
            ))
        return out

    def _symbol_components(self) -> list[Component]:
        out: list[Component] = []
        for sym in self.graph.all_symbols():
            # Filter trivial/noise symbols to keep component list meaningful
            if sym.name in _TRIVIAL_NAMES:
                continue
            if sym.kind == SymbolKind.FUNCTION and len(sym.name) < _MIN_SYMBOL_NAME_LEN:
                continue
            layer = infer_layer(sym.path)
            ctype = self._component_type(sym)
            purpose = self._symbol_purpose(sym)
            out.append(Component(
                id=f"{sym.kind.value}:{sym.path}:{sym.name}",
                name=sym.name, type=ctype, purpose=purpose,
                responsibilities=self._responsibilities(sym),
                dependencies=[c for c in sym.calls if c],
                location=sym.path, architectural_layer=layer,
                confidence=Confidence(score=0.85, rationale=f"{sym.kind.value} declaration"),
                evidence=[Evidence(file=sym.path, symbol=sym.name, reason="symbol declaration")],
            ))
        return out

    def _link(self, components: list[Component]) -> list[Component]:
        """Populate `consumers` by reversing dependencies in O(N) time."""
        dep_to_consumers: dict[str, set[str]] = {}
        for other in components:
            for dep in other.dependencies:
                dep_to_consumers.setdefault(dep, set()).add(other.name)

        for c in components:
            consumers: set[str] = set()
            if c.name in dep_to_consumers:
                consumers.update(dep_to_consumers[c.name])
            short_id = c.id.split(":")[-1]
            if short_id in dep_to_consumers:
                consumers.update(dep_to_consumers[short_id])
            consumers.discard(c.name)
            c.consumers = sorted(consumers)
        return components

    @staticmethod
    def _component_type(sym: Symbol) -> ComponentType:
        if sym.kind == SymbolKind.CLASS:
            return ComponentType.CLASS
        if sym.kind == SymbolKind.MODEL:
            return ComponentType.MODEL
        if sym.kind == SymbolKind.COMPONENT:
            return ComponentType.SERVICE
        if sym.kind in (SymbolKind.FUNCTION, SymbolKind.METHOD):
            # *Proxy() / *Plugin() / *Provider() convention → treat as service
            if sym.name.endswith(("Proxy", "Plugin", "Provider", "Handler", "Middleware")):
                return ComponentType.SERVICE
            if any("controller" in d or "route" in d or "api" in d for d in sym.decorators):
                return ComponentType.API_CONTROLLER
            return ComponentType.FUNCTION
        return ComponentType.MODULE

    @staticmethod
    def _module_purpose(path: str, module) -> str:
        if path.split("/")[-1] in _ENTRYPOINT_FILES:
            return "Application entrypoint / startup"
        return f"Module with {len(module.symbols)} symbol(s)"

    @staticmethod
    def _symbol_purpose(sym: Symbol) -> str:
        if sym.kind == SymbolKind.MODEL:
            return "Data model / schema"
        if sym.kind == SymbolKind.COMPONENT:
            return "UI component"
        if sym.docstring:
            return sym.docstring.strip().splitlines()[0][:120]
        if any("route" in d or "get" in d or "post" in d for d in sym.decorators):
            return "HTTP endpoint handler"
        if sym.name.endswith("Proxy"):
            provider = sym.name[:-5]  # strip 'Proxy'
            return f"Vite proxy plugin — proxies upstream data for {provider} provider"
        if sym.name.endswith("Plugin"):
            return f"Vite plugin — {sym.name}"
        if sym.name.endswith("Provider"):
            return f"Data provider — {sym.name}"
        return f"{sym.kind.value} {sym.name}"

    @staticmethod
    def _responsibilities(sym: Symbol) -> list[str]:
        resp: list[str] = []
        if sym.decorators:
            resp.append(f"decorated with {', '.join(sym.decorators[:3])}")
        if sym.bases:
            resp.append(f"extends {', '.join(sym.bases[:3])}")
        if sym.is_async:
            resp.append("async execution")
        return resp
