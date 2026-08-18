"""Architecture discovery: evidence-based pattern inference (never forced labels)."""

from __future__ import annotations

from app.analyzers.source_graph import SourceGraph
from app.domain.api_model import ApiSpec
from app.domain.architecture import ArchitectureLayer, ArchitecturePattern, ArchitectureReport
from app.domain.common import Confidence, Evidence
from app.domain.component import Component, ComponentType
from app.domain.technology import TechnologyStack


class ArchitectureDiscoverer:
    """Infers architecture from collected evidence with confidence scores."""

    def __init__(
        self,
        graph: SourceGraph,
        components: list[Component],
        stack: TechnologyStack,
        api_spec: ApiSpec,
    ) -> None:
        self.graph = graph
        self.components = components
        self.stack = stack
        self.api = api_spec

    def discover(self) -> ArchitectureReport:
        report = ArchitectureReport()
        evidence: list[str] = []

        modules = list(self.graph.modules.values())
        module_count = len(modules)
        entry_points = [
            m.path for m in modules if m.path.split("/")[-1] in
            {"main.py", "app.py", "index.py", "manage.py", "run.py", "wsgi.py", "asgi.py"}
        ]
        report.entry_points = entry_points

        # Layer diversity signals a layered architecture.
        layers_seen = {c.architectural_layer for c in self.components}
        report.layers = self._build_layers()

        has_api = bool(self.api.endpoints)
        has_services = any(c.type == ComponentType.SERVICE for c in self.components)
        has_repos = any("repository" in c.name.lower() or "repo" in c.name.lower() for c in self.components)
        has_domain = any(c.architectural_layer == "domain" for c in self.components)
        has_persistence = any(c.architectural_layer == "persistence" for c in self.components)
        has_background = any(c.architectural_layer == "background" for c in self.components)

        # Pattern scoring.
        patterns: list[ArchitecturePattern] = []

        layered_score = self._score(
            [has_api, has_services or has_domain, has_persistence, len(layers_seen) >= 3]
        )
        if layered_score > 0.5:
            patterns.append(ArchitecturePattern(
                name="Layered Architecture", confidence=layered_score,
                evidence=[
                    f"{len(layers_seen)} logical layer(s) present",
                    "HTTP API layer" if has_api else "no explicit API layer",
                ],
            ))

        modular_score = self._score([
            module_count > 8,
            len(layers_seen) >= 2,
            has_domain or has_services,
            not has_background,
        ])
        if modular_score > 0.5:
            patterns.append(ArchitecturePattern(
                name="Modular Monolith", confidence=modular_score,
                evidence=[
                    f"{module_count} modules",
                    "shared deployment surface (single entry point)" if entry_points else "",
                ],
            ))

        # Microservices: require multiple independent deployable service roots.
        # (A monolith with background jobs or example apps is NOT microservices.)
        service_roots = self._count_service_roots()
        if service_roots >= 2:
            micro_score = self._score([
                has_background or self._has_message_broker(),
                module_count > 40,
                True,
            ])
            patterns.append(ArchitecturePattern(
                name="Microservices", confidence=micro_score,
                evidence=[
                    f"{service_roots} independent service root(s)",
                    "message broker" if self._has_message_broker() else "background processing",
                ],
            ))

        clean_score = self._score([has_domain, has_services, has_repos, has_persistence])
        if clean_score > 0.5:
            patterns.append(ArchitecturePattern(
                name="Clean / Hexagonal", confidence=clean_score,
                evidence=[
                    "domain layer" if has_domain else "",
                    "repository abstraction" if has_repos else "",
                    "service layer" if has_services else "",
                ],
            ))

        if not patterns:
            patterns.append(ArchitecturePattern(
                name="Unstructured / Script", confidence=0.4,
                evidence=["no clear architectural signals detected"],
            ))

        patterns.sort(key=lambda p: -p.confidence)
        report.patterns = patterns
        report.primary_pattern = patterns[0].name if patterns else ""
        report.confidence = patterns[0].confidence if patterns else 0.0

        report.evidence = [
            Evidence(file="(repo)", reason=e) for e in evidence
        ]
        report.service_boundaries = sorted({c.architectural_layer for c in self.components})
        return report

    def _build_layers(self) -> list[ArchitectureLayer]:
        layers: dict[str, list[str]] = {}
        for c in self.components:
            layers.setdefault(c.architectural_layer, []).append(c.name)
        return [
            ArchitectureLayer(
                name=name, components=comps[:40],
                confidence=Confidence(score=0.6, rationale="path-based layer inference"),
            )
            for name, comps in sorted(layers.items())
        ]

    def _has_message_broker(self) -> bool:
        infra = {t.name.lower() for t in self.stack.infrastructure}
        return any(k in infra for k in ("rabbitmq", "kafka", "celery"))

    _SERVICE_EXCLUDED_TOP_DIRS = {
        "examples", "example", "tests", "test", "docs", "doc", "docs_src",
        "docs-src", "documentation", "tools", "scripts", "benchmarks",
        "benchmark", "contrib", "migrations", "samples", "sample", "demo",
    }
    _ENTRYPOINT_FILES = {
        "main.py", "app.py", "manage.py", "run.py", "index.py",
        "wsgi.py", "asgi.py", "server.py",
    }

    def _count_service_roots(self) -> int:
        """Count distinct top-level dirs whose entry point lives *directly*
        under them (e.g. ``services/auth/main.py``). Deeply-nested entry points
        (documentation examples, ``src/<pkg>/app.py`` trees, library modules
        named ``wsgi.py``) do not indicate an independently deployable service."""
        roots: set[str] = set()
        for path in self.graph.modules:
            parts = path.split("/")
            if len(parts) != 2:
                continue
            top = parts[0].lower()
            if top in self._SERVICE_EXCLUDED_TOP_DIRS:
                continue
            if parts[-1].lower() in self._ENTRYPOINT_FILES:
                roots.add(top)
        return len(roots)

    @staticmethod
    def _score(flags: list[bool]) -> float:
        if not flags:
            return 0.0
        return round(sum(flags) / len(flags), 2)
