"""Prompt compiler: turn a KnowledgePackage into a prioritized, token-budgeted
implementation prompt for frontier coding models.

This is the "transmission" half of KNOX's mission: the same extracted knowledge
that ``to_markdown`` renders as a flat dump is here re-rendered as an
*engineered* prompt — prioritized sections, an explicit rebuild plan, inferred
build/run commands, and chunking when the package exceeds a target token budget.

The main prompt is always self-contained (architecture + tech stack + rebuild
instructions + prioritized summaries). Full detail lists that do not fit are
pushed to ``chunks`` so a caller can stream them in a second pass.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.domain.api_model import ApiEndpoint
from app.domain.component import Component, ComponentType
from app.domain.data_model import DataEntity
from app.domain.knowledge import KnowledgePackage

# Rough English token estimate (~4 characters per token).
_CHARS_PER_TOKEN = 4

# Default section limits for the self-contained main prompt.
_TOP_COMPONENTS = 60
_TOP_ENTITIES = 80
_TOP_ENDPOINTS = 120
_TOP_WORKFLOWS = 40
_TOP_FACTS = 25

# Compact limits used when even the default summaries exceed the budget.
_COMPACT_COMPONENTS = 20
_COMPACT_ENTITIES = 30
_COMPACT_ENDPOINTS = 40
_COMPACT_WORKFLOWS = 15
_COMPACT_FACTS = 10


def estimate_tokens(text: str) -> int:
    """Rough token count for budget planning (English ~4 chars/token)."""
    return max(1, math.ceil(len(text) / _CHARS_PER_TOKEN))


@dataclass
class PromptChunk:
    id: str
    title: str
    content: str
    token_estimate: int = 0


@dataclass
class CompiledPrompt:
    main: str
    chunks: list[PromptChunk] = field(default_factory=list)
    total_tokens: int = 0
    truncated: bool = False


def _component_importance(c: Component, entry_points: set[str]) -> int:
    """Rank components by connectivity + architectural significance."""
    score = len(c.dependencies) + len(c.consumers)
    if c.type in {
        ComponentType.API_CONTROLLER,
        ComponentType.SERVICE,
        ComponentType.MIDDLEWARE,
        ComponentType.REPOSITORY,
        ComponentType.MODEL,
        ComponentType.WORKER,
    }:
        score += 4
    layer = (c.architectural_layer or "").lower()
    if layer in {"api", "application", "domain", "service", "persistence"}:
        score += 1
    if c.location in entry_points or c.name in entry_points:
        score += 5
    if c.responsibilities:
        score += min(len(c.responsibilities), 3)
    return score


def _render_component_line(c: Component) -> str:
    line = f"- `{c.name}` [{c.type.value}] ({c.architectural_layer or 'unknown'})"
    if c.purpose:
        line += f" — {c.purpose.strip()[:140]}"
    if c.responsibilities:
        line += f" — responsible for: {', '.join(c.responsibilities[:6])}"
    return line


def _render_components(pkg: KnowledgePackage, top_n: int) -> str:
    if not pkg.components:
        return "_(no components discovered)_\n"
    entry_points = set(pkg.architecture.entry_points)
    ranked = sorted(pkg.components, key=lambda c: -_component_importance(c, entry_points))
    lines = [f"Top {min(top_n, len(ranked))} of {len(ranked)} components (most significant first):", ""]
    for c in ranked[:top_n]:
        lines.append(_render_component_line(c))
        if c.dependencies:
            lines.append(f"    depends on: {', '.join(c.dependencies[:10])}")
    return "\n".join(lines) + "\n"


def _render_entity_line(e: DataEntity) -> str:
    cols = ", ".join(f"{c.name}:{c.type}" for c in e.columns[:15])
    more = f" (+{len(e.columns) - 15} more)" if len(e.columns) > 15 else ""
    return f"- `{e.name}` ({e.kind}) — {cols}{more}"


def _render_entities(pkg: KnowledgePackage, top_n: int) -> str:
    entities = pkg.data_model.entities
    if not entities:
        return "_(no data entities discovered)_\n"
    lines = [f"Data model — {min(top_n, len(entities))} of {len(entities)} entities:", ""]
    for e in entities[:top_n]:
        lines.append(_render_entity_line(e))
    if pkg.data_model.relationships:
        lines.append("")
        lines.append("Relationships:")
        for r in pkg.data_model.relationships[: top_n]:
            lines.append(f"- {r.source} {r.kind.value} {r.target}")
    return "\n".join(lines) + "\n"


def _render_endpoint_line(e: ApiEndpoint) -> str:
    line = f"- `{e.method.upper():6s} {e.path}` -> {e.handler or '(inline)'}"
    if e.request_schema:
        line += f"  req={e.request_schema}"
    if e.response_schema:
        line += f"  resp={e.response_schema}"
    if e.authentication:
        line += f"  auth={','.join(e.authentication)}"
    return line


def _render_endpoints(pkg: KnowledgePackage, top_n: int) -> str:
    endpoints = pkg.apis.endpoints
    if not endpoints:
        return "_(no HTTP endpoints discovered)_\n"
    lines = [f"API surface — {min(top_n, len(endpoints))} of {len(endpoints)} endpoints:", ""]
    for e in endpoints[:top_n]:
        lines.append(_render_endpoint_line(e))
    return "\n".join(lines) + "\n"


def _render_workflows(pkg: KnowledgePackage, top_n: int) -> str:
    workflows = pkg.workflows
    if not workflows:
        return "_(no workflows reconstructed)_\n"
    lines = [f"Workflows — {min(top_n, len(workflows))} of {len(workflows)}:", ""]
    for w in workflows[:top_n]:
        steps = " -> ".join(s.name for s in w.steps[:12])
        lines.append(f"- **{w.name}** (entry: {w.entry_point})")
        if steps:
            lines.append(f"    {steps}")
    return "\n".join(lines) + "\n"


def _render_tech_stack(pkg: KnowledgePackage) -> str:
    s = pkg.technologies.summary
    out = ["## Technology Stack", ""]
    for label, key in (
        ("Languages", "languages"),
        ("Frameworks", "frameworks"),
        ("Databases", "databases"),
        ("Infrastructure", "infrastructure"),
    ):
        names = s.get(key) or []
        out.append(f"- **{label}**: {', '.join(names) if names else '(not detected)'}")
    critical = [d for d in pkg.technologies.dependencies if d.criticality == "critical"]
    if critical:
        out.append(f"- **Critical dependencies**: {', '.join(d.name for d in critical[:20])}")
    return "\n".join(out) + "\n"


def _infer_build_steps(pkg: KnowledgePackage) -> list[str]:
    """Infer install/build/run/test commands from the detected stack (heuristic)."""
    langs = {t.name.lower() for t in pkg.technologies.languages}
    frameworks = {t.name.lower() for t in pkg.technologies.frameworks}
    steps: list[str] = []

    if "python" in langs:
        steps.append("pip install -r requirements.txt")
        if "django" in frameworks:
            steps += ["python manage.py migrate", "python manage.py runserver", "python manage.py test"]
        elif "fastapi" in frameworks:
            steps += ["uvicorn app.main:app --reload", "pytest"]
        elif "flask" in frameworks:
            steps += ["flask run", "pytest"]
        else:
            steps += ["pytest"]
    elif any(k in langs for k in ("javascript", "typescript")):
        steps += ["npm install", "npm start", "npm test"]
    elif "go" in langs:
        steps += ["go build ./...", "go test ./..."]
    elif "rust" in langs:
        steps += ["cargo build", "cargo test"]
    elif "java" in langs:
        steps += ["mvn -q verify"] if "spring" in frameworks else ["gradle build"]
    return steps


def _render_rebuild_instructions(pkg: KnowledgePackage) -> str:
    build = _infer_build_steps(pkg)
    build_lines = "\n".join(f"   {i}. {s}" for i, s in enumerate(build, 1)) or "   (see Technology Stack)"
    return (
        "## Rebuild Instructions\n\n"
        "Rebuild this project from scratch as a complete, working codebase. "
        "Follow this order:\n\n"
        "   1. **Scaffold** the project structure and dependency manifests for the Technology Stack.\n"
        "   2. **Data model** — implement every entity with its fields, types, and relationships.\n"
        "   3. **Core components** — implement the Components, preserving names, responsibilities, and dependencies.\n"
        "   4. **API surface** — implement every endpoint (method, path, request, response).\n"
        "   5. **Workflows** — wire each workflow end-to-end (entry -> steps -> outputs).\n"
        "   6. **Configuration** — expose the configuration/env contract (keys only; never invent secret values).\n"
        "   7. **Security** — apply the security requirements below.\n"
        "   8. **Tests** — add tests covering the acceptance criteria.\n"
        "   9. **Build & verify** with:\n"
        f"{build_lines}\n\n"
        "Rules:\n"
        "- Do not invent requirements beyond this spec; state any assumption explicitly.\n"
        "- Preserve names (components, entities, endpoints) so the result is recognizable.\n"
        "- Treat facts as observed truth, inferences as strong guidance, hypotheses as options.\n"
    )


def _render_facts(pkg: KnowledgePackage, top_n: int) -> str:
    facts = pkg.facts
    if not facts:
        return "_(no classified facts)_\n"
    lines = [f"Facts / inferences / hypotheses ({min(top_n, len(facts))} of {len(facts)}):", ""]
    for f in facts[:top_n]:
        lines.append(f"- [{f.kind.upper()}] ({f.confidence:.2f}) {f.fact}")
    return "\n".join(lines) + "\n"


def _render_config(pkg: KnowledgePackage) -> str:
    parts: list[str] = []
    if pkg.configuration:
        parts.append("## Configuration & Environment\n")
        for k, v in pkg.configuration.items():
            parts.append(f"- {k}: {v}")
        parts.append("")
    if pkg.integrations:
        parts.append("## Integrations\n")
        parts.extend(f"- {i}" for i in pkg.integrations)
        parts.append("")
    return "\n".join(parts)


def _render_concerns(pkg: KnowledgePackage) -> str:
    out: list[str] = []
    if pkg.security:
        out.append("## Security Requirements\n\n" + "\n".join(f"- {s}" for s in pkg.security) + "\n")
    if pkg.constraints:
        out.append("## Constraints\n\n" + "\n".join(f"- {s}" for s in pkg.constraints) + "\n")
    if pkg.invariants:
        out.append("## Invariants\n\n" + "\n".join(f"- {s}" for s in pkg.invariants) + "\n")
    if pkg.risks:
        out.append("## Risks\n\n" + "\n".join(f"- {s}" for s in pkg.risks) + "\n")
    return "\n".join(out)


def _render_evolution(pkg: KnowledgePackage) -> str:
    sprints = pkg.architectural_sprints.sprints
    if not sprints:
        return ""
    lines = ["## Evolution (architectural sprints)", ""]
    for s in sprints[:10]:
        lines.append(f"- **{s.name}** ({s.time_range[0]} -> {s.time_range[1]})")
        for change in s.architectural_changes[:5]:
            lines.append(f"    - {change}")
    return "\n".join(lines) + "\n"


def _render_plan(pkg: KnowledgePackage) -> str:
    spec = pkg.implementation_specification
    out: list[str] = []
    if spec.implementation_order:
        out.append("## Implementation Order\n\n" + "\n".join(f"{i+1}. {s}" for i, s in enumerate(spec.implementation_order)) + "\n")
    if spec.acceptance_criteria:
        out.append("## Acceptance Criteria\n\n" + "\n".join(f"- {s}" for s in spec.acceptance_criteria) + "\n")
    return "\n".join(out)


def _render_header(pkg: KnowledgePackage) -> str:
    repo = pkg.metadata.get("repository", "project")
    arch = pkg.architecture.primary_pattern or "undetermined"
    conf = pkg.architecture.confidence
    return (
        f"IMPLEMENT THIS ARCHITECTURE\n\n"
        f"Project: {repo}\n"
        f"Source: {pkg.metadata.get('source_url') or '(local)'}\n"
        f"Detected architecture: {arch} (confidence {conf:.2f})\n"
    )


def _render_architecture(pkg: KnowledgePackage) -> str:
    out = ["## Architecture", ""]
    for p in pkg.architecture.patterns[:8]:
        ev = "; ".join(e for e in p.evidence[:4] if e)
        out.append(f"- **{p.name}** (confidence {p.confidence:.2f})" + (f" — {ev}" if ev else ""))
    if pkg.architecture.layers:
        out.append("- Layers: " + ", ".join(layer.name for layer in pkg.architecture.layers))
    if pkg.architecture.entry_points:
        out.append("- Entry points: " + ", ".join(pkg.architecture.entry_points[:20]))
    return "\n".join(out) + "\n"


def _render_main(pkg: KnowledgePackage, compact: bool = False) -> str:
    c_top = _COMPACT_COMPONENTS if compact else _TOP_COMPONENTS
    e_top = _COMPACT_ENTITIES if compact else _TOP_ENTITIES
    a_top = _COMPACT_ENDPOINTS if compact else _TOP_ENDPOINTS
    w_top = _COMPACT_WORKFLOWS if compact else _TOP_WORKFLOWS
    f_top = _COMPACT_FACTS if compact else _TOP_FACTS

    sections = [
        _render_header(pkg),
        _render_architecture(pkg),
        _render_tech_stack(pkg),
        _render_rebuild_instructions(pkg),
        "## Components\n\n" + _render_components(pkg, c_top),
        "## Data Model\n\n" + _render_entities(pkg, e_top),
        "## API Surface\n\n" + _render_endpoints(pkg, a_top),
        "## Workflows\n\n" + _render_workflows(pkg, w_top),
        _render_config(pkg),
        _render_concerns(pkg),
        "## Facts / Inferences / Hypotheses\n\n" + _render_facts(pkg, f_top),
        _render_evolution(pkg),
        _render_plan(pkg),
    ]
    return "\n".join(s for s in sections if s)


def _full_detail_sections(pkg: KnowledgePackage) -> list[tuple[str, str, str]]:
    """Full (untruncated) detail blocks that may be chunked when over budget."""
    sections: list[tuple[str, str, str]] = []
    if pkg.components:
        body = "\n".join(_render_component_line(c) for c in sorted(
            pkg.components, key=lambda c: c.name.lower()
        ))
        sections.append(("components", "Full component list", "## Full Component List\n\n" + body + "\n"))
    if pkg.data_model.entities:
        body = "\n".join(_render_entity_line(e) for e in pkg.data_model.entities)
        sections.append(("data-model", "Full data model", "## Full Data Model\n\n" + body + "\n"))
    if pkg.apis.endpoints:
        body = "\n".join(_render_endpoint_line(e) for e in pkg.apis.endpoints)
        sections.append(("apis", "Full API surface", "## Full API Surface\n\n" + body + "\n"))
    if pkg.workflows:
        body = "\n".join(f"- **{w.name}** (entry: {w.entry_point}): " + " -> ".join(s.name for s in w.steps) for w in pkg.workflows)
        sections.append(("workflows", "Full workflow list", "## Full Workflow List\n\n" + body + "\n"))
    return sections


def _split_by_tokens(text: str, chunk_tokens: int) -> list[str]:
    """Split text into blocks no larger than ``chunk_tokens`` (on line boundaries)."""
    if chunk_tokens <= 0:
        return [text]
    target_chars = max(_CHARS_PER_TOKEN, chunk_tokens * _CHARS_PER_TOKEN)
    lines = text.splitlines(keepends=True)
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for line in lines:
        if current and current_len + len(line) > target_chars:
            chunks.append("".join(current))
            current = []
            current_len = 0
        current.append(line)
        current_len += len(line)
    if current:
        chunks.append("".join(current))
    return chunks


def compile_prompt(pkg: KnowledgePackage, max_tokens: int = 50000) -> CompiledPrompt:
    """Compile the knowledge package into a budgeted, prioritized prompt."""
    budget = max(1000, max_tokens)
    main = _render_main(pkg)
    main_tokens = estimate_tokens(main)

    # If even the summary prompt overflows, fall back to a compact rendering.
    if main_tokens > budget:
        main = _render_main(pkg, compact=True)
        main_tokens = estimate_tokens(main)

    chunks: list[PromptChunk] = []
    truncated = False

    for sec_id, title, full in _full_detail_sections(pkg):
        ft = estimate_tokens(full)
        if main_tokens + ft <= budget:
            main += "\n\n" + full
            main_tokens += ft
        else:
            chunk_budget = max(2000, budget - main_tokens)
            for i, chunk_text in enumerate(_split_by_tokens(full, chunk_budget), start=1):
                chunks.append(PromptChunk(
                    id=f"{sec_id}-{i}",
                    title=title,
                    content=chunk_text,
                    token_estimate=estimate_tokens(chunk_text),
                ))
            truncated = True

    total = main_tokens + sum(c.token_estimate for c in chunks)
    return CompiledPrompt(main=main, chunks=chunks, total_tokens=total, truncated=truncated)


def to_engineered_prompt(pkg: KnowledgePackage, max_tokens: int = 50000) -> str:
    """Return the self-contained main prompt (chunk contents are listed by id)."""
    compiled = compile_prompt(pkg, max_tokens)
    if compiled.chunks:
        listing = "\n\n## Additional Detail Chunks\n\n" + "\n".join(
            f"- `{c.id}` ({c.title}, ~{c.token_estimate} tokens)" for c in compiled.chunks
        )
        return compiled.main + listing
    return compiled.main
