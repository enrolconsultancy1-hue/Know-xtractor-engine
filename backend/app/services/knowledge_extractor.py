"""Knowledge assembly: turn intermediate results into the final KnowledgePackage."""

from __future__ import annotations

from typing import Any

from app.architecture.reconstruction import reconstruct_architecture
from app.domain.api_model import ApiSpec
from app.domain.architecture import ArchitectureReport
from app.domain.component import Component
from app.domain.data_model import DataModel
from app.domain.implementation import ImplementationSpec
from app.domain.knowledge import KnowledgeFact, KnowledgePackage
from app.domain.sprint import EvolutionTimeline
from app.domain.technology import TechnologyStack
from app.domain.workflow import Workflow


def assemble_knowledge(
    repository: str,
    source_url: str,
    stack: TechnologyStack,
    architecture: ArchitectureReport,
    components: list[Component],
    workflows: list[Workflow],
    data_model: DataModel,
    apis: ApiSpec,
    config: dict[str, Any],
    tests: list[dict[str, Any]],
    docs: dict[str, Any],
    timeline: EvolutionTimeline,
    integration_hints: list[str],
) -> KnowledgePackage:
    """Assemble the source-independent knowledge package."""
    pkg = KnowledgePackage.new(repository=repository, source_url=source_url)
    pkg.technologies = stack
    pkg.architecture = architecture
    pkg.components = components
    pkg.workflows = workflows
    pkg.data_model = data_model
    pkg.apis = apis
    pkg.configuration = config
    pkg.testing = tests
    pkg.architectural_sprints = timeline
    pkg.integrations = integration_hints

    # Patterns & anti-patterns & risks from evidence.
    pkg.patterns = [p.name for p in architecture.patterns]
    pkg.architectural_decisions = _decisions(stack, architecture, apis)
    pkg.invariants = _invariants(data_model, workflows)
    pkg.constraints = _constraints(stack, config)
    pkg.risks = _risks(components, workflows, apis)
    pkg.assumptions = [
        "Directory structure was used as a primary signal for layering",
        "Test files reflect intended behavior of the system",
        "Commit clustering approximates architectural evolution",
    ]
    pkg.security = _security_notes(config)

    # Facts / inferences / hypotheses.
    pkg.facts = _build_facts(stack, architecture, components, workflows, data_model, apis, timeline)

    # Hardcoded secrets surfaced as a security fact (locations only, never values).
    source_secrets = config.get("source_secrets") or []
    if source_secrets:
        top = sorted(source_secrets, key=lambda s: -float(s.get("confidence", 0)))[:5]
        pkg.facts.append(KnowledgeFact(
            id=f"fact-{len(pkg.facts) + 1:03d}",
            fact=f"{len(source_secrets)} hardcoded secret(s) detected in source",
            kind="inference", confidence=0.6, category="security",
            evidence=[{"file": s["file"], "reason": f"line {s['line']}: {s['key']}"} for s in top],
        ))

    # Reconstruction + implementation spec.
    pkg.reconstructed_architecture = reconstruct_architecture(pkg)
    pkg.implementation_specification = build_implementation_spec(pkg)

    return pkg


def _build_facts(
    stack: TechnologyStack,
    architecture: ArchitectureReport,
    components: list[Component],
    workflows: list[Workflow],
    data_model: DataModel,
    apis: ApiSpec,
    timeline: EvolutionTimeline,
) -> list[KnowledgeFact]:
    facts: list[KnowledgeFact] = []
    n = 0

    def add(fact: str, kind: str, confidence: float, evidence: list[dict], category: str) -> None:
        nonlocal n
        n += 1
        facts.append(KnowledgeFact(
            id=f"fact-{n:03d}", fact=fact, kind=kind,
            confidence=confidence, evidence=evidence, category=category,
        ))

    for lang in stack.languages:
        add(f"{lang.name} is present in the codebase", "fact", 0.95,
            [{"file": f"*.{lang.name.lower()}", "reason": "file extensions"}], "technology")
    for fw in stack.frameworks:
        add(f"{fw.name} is used as a framework", "fact", 0.85,
            [{"file": e.file, "reason": e.reason} for e in fw.evidence], "technology")
    for db in stack.databases:
        add(f"{db.name} is used for persistence", "fact", 0.8,
            [{"file": e.file, "reason": e.reason} for e in db.evidence], "data")

    if architecture.primary_pattern:
        add(
            f"The system follows a {architecture.primary_pattern} architecture",
            "inference", architecture.confidence,
            [{"file": "(repo)", "reason": "evidence-weighted pattern scoring"}], "architecture",
        )

    if apis.endpoints:
        add(f"The system exposes {len(apis.endpoints)} HTTP endpoint(s)", "fact", 0.85,
            [{"file": apis.endpoints[0].file, "reason": "route registration"}], "api")

    if data_model.entities:
        add(f"The domain model contains {len(data_model.entities)} entity/entities", "fact", 0.8,
            [{"file": e.source_file, "reason": "model declaration"} for e in data_model.entities[:3]], "data")

    if workflows:
        add(f"{len(workflows)} workflow(s) were reconstructed", "inference", 0.7,
            [{"file": w.entry_point, "reason": "entry point"} for w in workflows[:3]], "workflow")

    persistence_flows = [w for w in workflows if any(s.kind == "persistence" for s in w.steps)]
    external_flows = [w for w in workflows if any(s.kind == "external" for s in w.steps)]
    queue_flows = [w for w in workflows if any(s.kind == "queue" for s in w.steps)]
    if persistence_flows:
        add(f"{len(persistence_flows)} workflow(s) reach the persistence layer", "inference", 0.7,
            [{"file": w.entry_point, "reason": "call graph traces to database access"} for w in persistence_flows[:3]], "data")
    if external_flows:
        add(f"{len(external_flows)} workflow(s) call external services", "inference", 0.6,
            [{"file": w.entry_point, "reason": "call graph traces to network access"} for w in external_flows[:3]], "integration")
    if queue_flows:
        add(f"{len(queue_flows)} workflow(s) enqueue background work", "inference", 0.6,
            [{"file": w.entry_point, "reason": "call graph traces to a message broker"} for w in queue_flows[:3]], "integration")

    sample = next((w for w in workflows if len(w.steps) >= 3), None)
    if sample:
        chain = " -> ".join(s.name for s in sample.steps[:8])
        add(f"Request lifecycle: {chain}", "inference", 0.6,
            [{"file": sample.entry_point, "reason": "recursive call-graph trace"}], "workflow")

    if timeline.sprints:
        add(f"{len(timeline.sprints)} architectural sprint(s) identified", "inference", 0.6,
            [{"file": "git", "reason": "commit clustering"}], "evolution")

    if any(c.architectural_layer == "domain" for c in components) and any(
        c.architectural_layer == "persistence" for c in components
    ):
        add("The project separates domain concerns from persistence", "hypothesis", 0.5,
            [{"file": "(repo)", "reason": "layer separation observed"}], "architecture")

    return facts


def _decisions(stack: TechnologyStack, architecture: ArchitectureReport, apis: ApiSpec) -> list[str]:
    out: list[str] = []
    fw = [t.name for t in stack.frameworks]
    if fw:
        out.append(f"Use {', '.join(fw)} as the application framework")
    if apis.framework:
        out.append(f"Expose the API via {apis.framework}")
    if stack.databases:
        out.append(f"Persist data using {', '.join(t.name for t in stack.databases)}")
    if architecture.primary_pattern:
        out.append(f"Adopt a {architecture.primary_pattern} structure")
    return out


def _invariants(data_model: DataModel, workflows: list[Workflow]) -> list[str]:
    out: list[str] = []
    for rel in data_model.relationships:
        out.append(f"{rel.source} relates to {rel.target} ({rel.kind.value})")
    if not out:
        out.append("No explicit data invariants detected")
    return out


def _constraints(stack: TechnologyStack, config: dict[str, Any]) -> list[str]:
    out: list[str] = []
    secrets = config.get("secret_required", [])
    for s in secrets[:10]:
        out.append(f"Requires secret/env: {s}")
    if stack.databases:
        out.append(f"Requires {', '.join(t.name for t in stack.databases)} connectivity")
    return out or ["No explicit constraints detected"]


def _risks(components: list[Component], workflows: list[Workflow], apis: ApiSpec) -> list[str]:
    out: list[str] = []
    if not apis.endpoints and not workflows:
        out.append("No API or workflow surface detected — verify analysis depth")
    if not components:
        out.append("No components extracted — source may be unsupported or empty")
    if len(components) > 500:
        out.append("Large component count may indicate low cohesion")
    return out or ["No significant risks detected"]


def _security_notes(config: dict[str, Any]) -> list[str]:
    out: list[str] = []
    secrets = config.get("secret_required", [])
    if secrets:
        out.append(f"{len(secrets)} secret key(s) identified (values redacted)")
    source_secrets = config.get("source_secrets") or []
    if source_secrets:
        out.append(f"{len(source_secrets)} hardcoded secret(s) flagged in source (locations only)")
    out.append("Repository code is never executed during analysis")
    return out


def build_implementation_spec(pkg: KnowledgePackage) -> ImplementationSpec:
    """Produce an implementation-ready specification from the knowledge package."""
    spec = ImplementationSpec()
    spec.project_objective = (
        f"Reimplement the system described by {pkg.metadata.get('repository', 'the source')} "
        "using its extracted knowledge (workflows, domain model, interfaces)."
    )

    spec.functional_requirements = [w.name for w in pkg.workflows] or [
        "Functional requirements could not be fully inferred; inspect components"
    ]
    spec.non_functional_requirements = [
        "Performance: meet the response characteristics implied by the original architecture",
        "Security: never expose secrets; validate all inputs",
        "Reliability: handle failure paths discovered in the original system",
    ]
    spec.architecture = [
        f"Pattern: {pkg.architecture.primary_pattern or 'layered'}",
        *[f"Layer: {layer.name}" for layer in pkg.architecture.layers],
    ]
    spec.technology_stack = {
        b.concern: b.selected for b in pkg.reconstructed_architecture.technology_bindings
    }
    spec.domain_model = [f"{e.name}: {', '.join(c.name for c in e.columns[:8])}" for e in pkg.data_model.entities]
    spec.api_specification = [
        f"{ep.method.upper()} {ep.path} -> {ep.handler or 'handler'}" for ep in pkg.apis.endpoints
    ]
    spec.workflows = [w.name for w in pkg.workflows]
    spec.database = [
        *[f"Entity {e.name} ({e.source_kind})" for e in pkg.data_model.entities],
        *[f"Rel: {r.source} -> {r.target} ({r.kind.value})" for r in pkg.data_model.relationships],
    ]
    spec.configuration = [
        *[f"ENV: {k}" for k in pkg.configuration.get("env_vars", [])],
        *[f"Config key: {k}" for k in sorted(pkg.configuration.get("keys", {}))],
        *[f"Secret: {k}" for k in pkg.configuration.get("secret_required", [])],
    ]
    spec.security = pkg.security
    spec.testing = [
        f"Test file {t['file']} ({t['test_count']} tests)" for t in pkg.testing[:20]
    ] or ["Add unit tests for each component"]
    spec.deployment = [
        b.selected for b in pkg.reconstructed_architecture.technology_bindings
        if b.concern == "deployment"
    ] or ["Containerize with Docker; serve via a reverse proxy"]
    spec.implementation_order = _implementation_order(pkg)
    spec.acceptance_criteria = _acceptance_criteria(pkg)
    return spec


def _implementation_order(pkg: KnowledgePackage) -> list[str]:
    order = [
        "Project scaffold + configuration + logging",
        "Domain model (entities and relationships)",
        "Persistence layer (repositories / migrations)",
    ]
    if pkg.apis.endpoints:
        order.append("API layer (routes, schemas, validation)")
    if pkg.workflows:
        order.append("Application services implementing the workflows")
    order.append("Frontend / presentation layer")
    order.append("Background jobs (if required)")
    order.append("Tests (unit + integration)")
    order.append("Deployment + CI/CD")
    return order


def _acceptance_criteria(pkg: KnowledgePackage) -> list[str]:
    out = [
        "All functional requirements are implemented and verified",
        "The reconstructed workflows are executable end-to-end",
    ]
    if pkg.apis.endpoints:
        out.append(f"All {len(pkg.apis.endpoints)} API endpoint(s) respond per specification")
    out.append("No secrets are hardcoded; configuration is externalized")
    out.append("Tests pass and cover the core workflows")
    return out
