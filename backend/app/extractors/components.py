"""Component discovery: turn symbols + modules into architectural components."""

from __future__ import annotations

from app.analyzers.source_graph import SourceGraph, Symbol, SymbolKind
from app.domain.common import Confidence, Evidence
from app.domain.component import Component, ComponentType

_LAYER_BY_PATH: list[tuple[tuple[str, ...], str]] = [
    (("api", "controllers", "routes", "views", "endpoints", "handlers", "routers"), "presentation"),
    (("services", "application", "usecases", "use_cases", "biz", "business"), "application"),
    (("domain", "models", "entities", "core", "schema"), "domain"),
    (("repositories", "repository", "dao", "db", "database", "infra", "persistence", "storage"), "persistence"),
    (("config", "settings", "configuration", "env"), "configuration"),
    (("tests", "test"), "testing"),
    (("middleware", "middlewares", "interceptors"), "middleware"),
    (("worker", "workers", "jobs", "tasks", "queue", "celery"), "background"),
    (("cli", "commands", "scripts"), "cli"),
]

_ENTRYPOINT_FILES = {"main.py", "app.py", "index.py", "manage.py", "run.py", "wsgi.py", "asgi.py"}


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
        """Populate `consumers` by reversing dependencies."""
        for c in components:
            c.consumers = sorted({
                other.name
                for other in components
                if c.name in other.dependencies or c.id.split(":")[-1] in other.dependencies
                if other.id != c.id
            })
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
