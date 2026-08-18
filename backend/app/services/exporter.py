"""Export the knowledge package to JSON, YAML, Markdown, and PDF."""

from __future__ import annotations

from pathlib import Path

import yaml
from fpdf import FPDF

from app.core.security import redact_secrets
from app.domain.knowledge import KnowledgePackage


def to_json(pkg: KnowledgePackage) -> str:
    return pkg.model_dump_json(indent=2)


def to_yaml(pkg: KnowledgePackage) -> str:
    return yaml.safe_dump(pkg.model_dump(mode="json"), sort_keys=False, allow_unicode=True)


def to_markdown(pkg: KnowledgePackage) -> str:
    s = pkg.stats()
    lines: list[str] = [
        f"# KNOX Knowledge Package: {pkg.metadata.get('repository', 'unknown')}",
        "",
        f"- Source: {pkg.metadata.get('source_url') or '(local)'}",
        f"- Generated: {pkg.metadata.get('generated_at', '')}",
        f"- Architecture: {s['primary_pattern'] or 'undetermined'} (confidence {s['confidence']})",
        "",
        "## Technology Stack",
    ]
    for kind, names in s["technologies"].items():
        if names:
            lines.append(f"- **{kind}**: {', '.join(names)}")

    lines.append("\n## Components")
    for c in pkg.components:
        lines.append(f"- `{c.name}` [{c.type.value}] ({c.architectural_layer}) — {c.purpose[:100]}")

    lines.append("\n## Workflows")
    for w in pkg.workflows:
        lines.append(f"- **{w.name}** (entry: {w.entry_point})")
        for step in w.steps:
            lines.append(f"    - {step.kind}: {step.name}")

    lines.append("\n## APIs")
    for ep in pkg.apis.endpoints:
        lines.append(f"- `{ep.method.upper()} {ep.path}` -> {ep.handler or 'handler'}")

    lines.append("\n## Data Model")
    for e in pkg.data_model.entities:
        cols = ", ".join(c.name for c in e.columns)
        lines.append(f"- **{e.name}** ({e.source_kind}): {cols}")
    for r in pkg.data_model.relationships:
        lines.append(f"- {r.source} {r.kind.value} {r.target}")

    lines.append("\n## Architectural Sprints")
    lines.append(pkg.architectural_sprints.as_text())

    lines.append("\n## Facts / Inferences / Hypotheses")
    for f in pkg.facts:
        lines.append(f"- [{f.kind.upper()}] ({f.confidence:.2f}) {f.fact}")

    lines.append("\n## Risks")
    for risk in pkg.risks:
        lines.append(f"- {risk}")

    lines.append("\n## Implementation Specification")
    lines.append(pkg.implementation_specification.to_prompt(pkg.metadata.get("repository", "project")))
    return redact_secrets("\n".join(lines))


def to_pdf(pkg: KnowledgePackage) -> bytes:
    """Render a simple, readable PDF (text layout via fpdf2)."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, f"KNOX Knowledge Package: {pkg.metadata.get('repository', '')}", ln=True)
    pdf.set_font("Helvetica", "", 10)
    for line in to_markdown(pkg).splitlines():
        if line.startswith("# "):
            pdf.set_font("Helvetica", "B", 13)
            pdf.cell(0, 8, line.lstrip("# ").strip(), ln=True)
            pdf.set_font("Helvetica", "", 9)
        elif line.startswith("## "):
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 7, line.lstrip("# ").strip(), ln=True)
            pdf.set_font("Helvetica", "", 9)
        else:
            # Wrap long lines.
            safe = line.encode("latin-1", "replace").decode("latin-1")
            pdf.multi_cell(0, 5, safe[:200])
    return bytes(pdf.output())


def export_package(pkg: KnowledgePackage, fmt: str, out_dir: Path) -> Path:
    """Export to the given format, returning the output path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    name = pkg.metadata.get("repository", "knowledge")
    safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name) or "knowledge"

    if fmt == "json":
        path = out_dir / f"{safe_name}.json"
        path.write_text(to_json(pkg), encoding="utf-8")
    elif fmt in ("yaml", "yml"):
        path = out_dir / f"{safe_name}.yaml"
        path.write_text(to_yaml(pkg), encoding="utf-8")
    elif fmt == "pdf":
        path = out_dir / f"{safe_name}.pdf"
        path.write_bytes(to_pdf(pkg))
    else:  # markdown default
        path = out_dir / f"{safe_name}.md"
        path.write_text(to_markdown(pkg), encoding="utf-8")
    return path
