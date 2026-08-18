"""Workflow discovery: reconstruct end-to-end flows from entry points and APIs."""

from __future__ import annotations

from app.analyzers.callgraph import CallGraph, CallKind
from app.analyzers.source_graph import SourceGraph, Symbol
from app.domain.api_model import ApiSpec
from app.domain.common import Confidence, Evidence
from app.domain.workflow import Workflow, WorkflowStep

_ENTRYPOINT_FILES = {"main.py", "app.py", "index.py", "manage.py", "run.py", "cli.py"}


class WorkflowExtractor:
    """Builds workflow graphs from API endpoints and entry-point call chains."""

    def __init__(self, graph: SourceGraph, api_spec: ApiSpec, callgraph: CallGraph | None = None) -> None:
        self.graph = graph
        self.api = api_spec
        self.callgraph = callgraph
        self._symbol_index: dict[str, Symbol] = {}
        self._by_id: dict[str, Symbol] = {}
        for sym in graph.all_symbols():
            self._symbol_index[sym.name] = sym
            self._by_id[f"{sym.path}:{sym.name}"] = sym

    def extract(self) -> list[Workflow]:
        workflows: list[Workflow] = []
        workflows.extend(self._api_workflows())
        workflows.extend(self._entrypoint_workflows())
        return [w for w in workflows if w.steps]

    def _api_workflows(self) -> list[Workflow]:
        out: list[Workflow] = []
        for ep in self.api.endpoints:
            steps: list[WorkflowStep] = []
            steps.append(WorkflowStep(
                id="trigger", name=f"{ep.method.upper()} {ep.path}",
                kind="trigger", component_id=ep.handler,
                description="Incoming HTTP request",
            ))
            prev = "trigger"
            handler = self._by_id.get(f"{ep.file}:{ep.handler}") or self._symbol_index.get(ep.handler)
            if handler and self.callgraph is not None:
                trace = self.callgraph.trace(CallGraph.symbol_id(handler))
                for i, (label, kind, _depth) in enumerate(trace[:12]):
                    sid = f"step{i}"
                    steps.append(WorkflowStep(
                        id=sid, name=label, kind=self._step_kind(kind),
                        component_id=label, dependencies=[prev],
                        description=f"Data-flow: {kind.value}",
                    ))
                    prev = sid
            elif handler:
                for i, call in enumerate(self._distinct(handler.calls)[:8]):
                    sid = f"step{i}"
                    steps.append(WorkflowStep(
                        id=sid, name=call, kind="transform",
                        component_id=call, dependencies=[prev],
                        description=f"Called by {ep.handler}",
                    ))
                    prev = sid
            steps.append(WorkflowStep(
                id="output", name="HTTP response", kind="output",
                dependencies=[prev], description="Response returned to client",
            ))
            out.append(Workflow(
                id=f"workflow:api:{ep.method}:{ep.path}",
                name=f"API {ep.method.upper()} {ep.path}",
                entry_point=ep.handler or f"{ep.method} {ep.path}",
                trigger=f"{ep.method.upper()} {ep.path}",
                description=f"HTTP request workflow for {ep.method.upper()} {ep.path}",
                steps=steps,
                outputs=["HTTP response"],
                confidence=Confidence(score=0.75, rationale="route-derived workflow"),
                evidence=[Evidence(file=ep.file, symbol=ep.handler, reason="route handler")],
            ))
        return out

    def _entrypoint_workflows(self) -> list[Workflow]:
        out: list[Workflow] = []
        for path, module in self.graph.modules.items():
            if path.split("/")[-1] not in _ENTRYPOINT_FILES:
                continue
            entry_symbols = [
                s for s in module.symbols
                if s.kind.value in ("function",) and (s.name in {"main", "run", "app"} or "__main__" in s.calls)
            ]
            if not entry_symbols:
                entry_symbols = [s for s in module.symbols if s.kind.value == "function"][:1]
            for sym in entry_symbols:
                steps = [WorkflowStep(
                    id="start", name=f"{sym.name}()", kind="trigger",
                    component_id=sym.name, description="Program entry point",
                )]
                prev = "start"
                for i, call in enumerate(self._distinct(sym.calls)[:8]):
                    sid = f"call{i}"
                    steps.append(WorkflowStep(
                        id=sid, name=call, kind="transform",
                        component_id=call, dependencies=[prev],
                    ))
                    prev = sid
                steps.append(WorkflowStep(
                    id="end", name="exit", kind="output", dependencies=[prev],
                ))
                out.append(Workflow(
                    id=f"workflow:entry:{path}:{sym.name}",
                    name=f"Startup: {sym.name}()",
                    entry_point=f"{path}:{sym.name}",
                    trigger="Application startup / CLI invocation",
                    steps=steps,
                    outputs=["process exit"],
                    confidence=Confidence(score=0.7, rationale="entry-point call chain"),
                    evidence=[Evidence(file=path, symbol=sym.name, reason="entry point")],
                ))
        return out

    @staticmethod
    def _distinct(items: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for i in items:
            if i not in seen and i.strip():
                seen.add(i)
                out.append(i)
        return out

    @staticmethod
    def _step_kind(kind: CallKind) -> str:
        if kind is CallKind.PERSISTENCE:
            return "persistence"
        if kind is CallKind.EXTERNAL:
            return "external"
        if kind is CallKind.QUEUE:
            return "queue"
        if kind is CallKind.CACHE:
            return "cache"
        return "transform"
