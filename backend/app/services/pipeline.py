"""The analysis pipeline engine: orchestrates all analyzers into a knowledge package."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.analyzers.api_analyzer import ApiAnalyzer
from app.analyzers.base import AnalyzerRegistry, registry
from app.analyzers.config_analyzer import ConfigAnalyzer
from app.analyzers.data_analyzer import DataAnalyzer
from app.analyzers.dependencies import DependencyAnalyzer
from app.analyzers.doc_analyzer import DocumentationAnalyzer
from app.analyzers.generic import GenericAnalyzer
from app.analyzers.inventory import FileInventory
from app.analyzers.languages import LanguageDetector
from app.analyzers.python import PythonAnalyzer
from app.analyzers.source_graph import FileEntry, SourceGraph
from app.analyzers.test_analyzer import TestAnalyzer
from app.analyzers.treesitter import TreeSitterJsAnalyzer
from app.architecture.discovery import ArchitectureDiscoverer
from app.domain.api_model import ApiSpec
from app.domain.architecture import ArchitectureReport
from app.domain.component import Component
from app.domain.data_model import DataModel
from app.domain.knowledge import KnowledgePackage
from app.domain.sprint import CommitInfo, EvolutionTimeline
from app.domain.technology import TechnologyStack
from app.domain.workflow import Workflow
from app.extractors.components import ComponentExtractor
from app.extractors.workflows import WorkflowExtractor
from app.git.history import GitHistory
from app.git.sprints import cluster_sprints
from app.services.knowledge_extractor import assemble_knowledge

ProgressCallback = Callable[[str, float, str], None]

# Register analyzers once.
_registered = False


def _register_default_analyzers() -> AnalyzerRegistry:
    global _registered
    if not _registered:
        for analyzer in (
            LanguageDetector(),
            DependencyAnalyzer(),
            PythonAnalyzer(),
            TreeSitterJsAnalyzer(),
            GenericAnalyzer(),
            ApiAnalyzer(),
            DataAnalyzer(),
            ConfigAnalyzer(),
            TestAnalyzer(),
            DocumentationAnalyzer(),
        ):
            registry.register(analyzer)
        _registered = True
    return registry


@dataclass
class PipelineContext:
    """Intermediate state shared across pipeline stages."""

    repository: str = ""
    source_url: str = ""
    repo_path: str = ""
    inventory: list[FileEntry] = field(default_factory=list)
    graph: SourceGraph = field(default_factory=SourceGraph)
    stack: TechnologyStack = field(default_factory=TechnologyStack)
    components: list[Component] = field(default_factory=list)
    workflows: list[Workflow] = field(default_factory=list)
    apis: ApiSpec = field(default_factory=ApiSpec)
    data_model: DataModel = field(default_factory=DataModel)
    config: dict[str, Any] = field(default_factory=dict)
    tests: list[dict[str, Any]] = field(default_factory=list)
    docs: dict[str, Any] = field(default_factory=dict)
    commits: list[CommitInfo] = field(default_factory=list)
    timeline: EvolutionTimeline = field(default_factory=EvolutionTimeline)
    architecture: ArchitectureReport = field(default_factory=ArchitectureReport)
    pkg: KnowledgePackage | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class AnalysisPipeline:
    """Runs the full repository -> knowledge package pipeline."""

    def __init__(self) -> None:
        self.registry = _register_default_analyzers()

    def run(self, ctx: PipelineContext, progress: ProgressCallback | None = None) -> KnowledgePackage:
        cb = progress or (lambda stage, pct, msg: None)

        # 1. File inventory.
        cb("file_inventory", 0.05, "Scanning repository files")
        inventory = FileInventory(ctx.repo_path).scan()
        ctx.inventory = inventory
        ctx.warnings.extend(
            f"Oversized file skipped: {f.path}" for f in inventory if f.is_binary and f.size > 0
        )

        # 2. Language detection.
        cb("language_detection", 0.15, "Detecting languages and technologies")
        ctx.stack = self.registry.require("languages").analyze(ctx.repo_path, inventory, ctx.graph, {})

        # 3. Static analysis (source parsing).
        cb("static_analysis", 0.30, "Parsing source code (AST)")
        source_files = FileInventory.source_files(inventory)
        analyzers = self.registry.select(inventory)
        analyzer_ctx: dict[str, Any] = {"technologies": ctx.stack}
        for analyzer in analyzers:
            if analyzer.name in ("languages", "dependencies", "api", "data", "config", "tests", "docs"):
                continue
            try:
                analyzer.analyze(ctx.repo_path, source_files, ctx.graph, analyzer_ctx)
            except Exception as exc:  # noqa: BLE001 — analyzer isolation
                ctx.warnings.append(f"Analyzer {analyzer.name} failed: {exc}")

        # 4. Dependency analysis.
        cb("dependency_analysis", 0.45, "Analyzing dependencies")
        if self.registry.require("dependencies").applicable(inventory):
            ctx.stack.dependencies = self.registry.require("dependencies").analyze(
                ctx.repo_path, inventory, ctx.graph, analyzer_ctx
            )

        # 5. API + data + config + tests + docs.
        cb("api_discovery", 0.55, "Discovering APIs and data model")
        ctx.apis = self.registry.require("api").analyze(ctx.repo_path, inventory, ctx.graph, analyzer_ctx)
        ctx.data_model = self.registry.require("data").analyze(ctx.repo_path, inventory, ctx.graph, analyzer_ctx)
        ctx.config = self.registry.require("config").analyze(ctx.repo_path, inventory, ctx.graph, analyzer_ctx)
        ctx.tests = self.registry.require("tests").analyze(ctx.repo_path, inventory, ctx.graph, analyzer_ctx)
        ctx.docs = self.registry.require("docs").analyze(ctx.repo_path, inventory, ctx.graph, analyzer_ctx)

        # 6. Component discovery.
        ctx.components = ComponentExtractor(ctx.graph).extract()

        # 7. Workflow extraction.
        cb("workflow_extraction", 0.65, "Reconstructing workflows")
        ctx.workflows = WorkflowExtractor(ctx.graph, ctx.apis).extract()

        # 8. Architecture discovery.
        cb("architecture_discovery", 0.75, "Inferring architecture")
        ctx.architecture = ArchitectureDiscoverer(
            ctx.graph, ctx.components, ctx.stack, ctx.apis
        ).discover()

        # 9. Git analysis.
        cb("git_analysis", 0.85, "Analyzing git history")
        git = GitHistory(ctx.repo_path)
        ctx.commits = git.commits()
        ctx.timeline = cluster_sprints(ctx.commits)

        # 10. Knowledge synthesis.
        cb("knowledge_synthesis", 0.92, "Synthesizing knowledge package")
        ctx.pkg = assemble_knowledge(
            repository=ctx.repository,
            source_url=ctx.source_url,
            stack=ctx.stack,
            architecture=ctx.architecture,
            components=ctx.components,
            workflows=ctx.workflows,
            data_model=ctx.data_model,
            apis=ctx.apis,
            config=ctx.config,
            tests=ctx.tests,
            docs=ctx.docs,
            timeline=ctx.timeline,
            integration_hints=self._integration_hints(ctx),
        )

        cb("architecture_reconstruction", 0.98, "Reconstructing architecture")
        ctx.pkg.reconstructed_architecture = ctx.pkg.reconstructed_architecture or ctx.pkg.reconstructed_architecture

        cb("done", 1.0, "Analysis complete")
        return ctx.pkg

    @staticmethod
    def _integration_hints(ctx: PipelineContext) -> list[str]:
        hints: set[str] = set()
        for m in ctx.graph.modules.values():
            for imp in m.imports:
                root = imp.module.split(".")[0]
                if root not in ("os", "sys", "json", "re", "typing", "abc", "pathlib", "datetime",
                                "collections", "functools", "itertools", "logging", "enum", "math",
                                "random", "string", "io", "time", "asyncio", "contextlib", "copy"):
                    hints.add(root)
        return sorted(hints)[:40]
