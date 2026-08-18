"""Demo: run the full KNOX pipeline on a repository and print the result."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.pipeline import AnalysisPipeline, PipelineContext

TARGET = r"C:\Users\HP\Projects\knox"


def main() -> None:
    ctx = PipelineContext(repository="knox", source_url="https://github.com/enrolconsultancy1-hue/Know-xtractor-engine.git",
                          repo_path=TARGET)
    stages: list[str] = []
    pkg = AnalysisPipeline().run(ctx, lambda s, p, m: stages.append(s))

    print("=== PIPELINE STAGES ===")
    for s in stages:
        print("  -", s)

    stats = pkg.stats()
    print("\n=== STATS ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")

    print("\n=== ARCHITECTURE PATTERNS ===")
    for p in pkg.architecture.patterns:
        print(f"  {p.name}: {p.confidence:.2f}")

    print("\n=== FACTS (first 12) ===")
    for f in pkg.facts[:12]:
        print(f"  [{f.kind.upper():10s}] ({f.confidence:.2f}) {f.fact}")

    print("\n=== COMPONENTS (first 8) ===")
    for c in pkg.components[:8]:
        print(f"  {c.type.value:12s} {c.name:24s} layer={c.architectural_layer}")

    print("\n=== WORKFLOWS ===")
    for w in pkg.workflows[:6]:
        print(f"  {w.name} -> {[s.name for s in w.steps]}")

    print("\n=== APIS ===")
    for e in pkg.apis.endpoints[:12]:
        print(f"  {e.method.upper():6s} {e.path:24s} {e.handler}")

    print("\n=== DATA MODEL ===")
    for e in pkg.data_model.entities:
        print(f"  {e.name} ({e.source_kind}): {[c.name for c in e.columns]}")

    print("\n=== SPRINTS ===")
    for sp in pkg.architectural_sprints.sprints:
        print(f"  {sp.id}: {sp.name} ({len(sp.commits)} commits)")

    print("\n=== TECH STACK ===")
    print(" ", pkg.technologies.summary)

    print("\n=== RECONSTRUCTION BINDINGS ===")
    for b in pkg.reconstructed_architecture.technology_bindings:
        print(f"  {b.concern}: {b.selected}")

    # Export.
    spec = pkg.implementation_specification
    prompt = spec.to_prompt("knox")
    print("\n=== IMPLEMENTATION PROMPT (first 600 chars) ===")
    print(prompt[:600])

    # Persist a JSON copy next to the demo output.
    demo_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exports")
    os.makedirs(demo_dir, exist_ok=True)
    json_path = os.path.join(demo_dir, "knox_knowledge_package.json")
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(pkg.model_dump_json(indent=2))
    md_path = os.path.join(demo_dir, "knox_knowledge_package.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(prompt)
    print(f"\nSaved: {json_path}")
    print(f"Saved: {md_path}")


if __name__ == "__main__":
    main()
