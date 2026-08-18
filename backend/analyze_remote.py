"""Analyze a real remote repository: clone + full pipeline + save the package."""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.config import get_settings
from app.services.acquisition import acquire_repository
from app.services.pipeline import AnalysisPipeline, PipelineContext

URL = sys.argv[1] if len(sys.argv) > 1 else "https://github.com/pallets/flask.git"
BRANCH = sys.argv[2] if len(sys.argv) > 2 else "main"


def main() -> None:
    settings = get_settings()
    slug = URL.rstrip("/").split("/")[-1].removesuffix(".git")
    workspace = settings.workspace_dir / "demo_remote" / slug

    print(f"=== Cloning {URL} (branch={BRANCH}) ===")
    t0 = time.time()
    repo_path = acquire_repository(URL, workspace, BRANCH)
    print(f"    cloned to {repo_path} in {time.time() - t0:.1f}s")

    ctx = PipelineContext(repository=slug, source_url=URL, repo_path=str(repo_path))
    stages: list[str] = []
    t0 = time.time()
    pkg = AnalysisPipeline().run(ctx, lambda s, p, m: stages.append(s))
    elapsed = time.time() - t0

    stats = pkg.stats()
    print(f"\n=== Analyzed {slug} in {elapsed:.1f}s ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")

    print("\n=== Architecture ===")
    for p in pkg.architecture.patterns[:5]:
        print(f"  {p.name}: {p.confidence:.2f}")

    print("\n=== Top facts ===")
    for f in pkg.facts[:10]:
        print(f"  [{f.kind.upper():10s}] ({f.confidence:.2f}) {f.fact}")

    print(f"\n=== Components: {len(pkg.components)}, Workflows: {len(pkg.workflows)}, "
          f"APIs: {len(pkg.apis.endpoints)}, Entities: {len(pkg.data_model.entities)} ===")
    print("=== Sample components ===")
    for c in pkg.components[:6]:
        print(f"  {c.type.value:12s} {c.name:28s} layer={c.architectural_layer}")

    out_dir = settings.exports_dir / "demo_remote"
    out_dir.mkdir(parents=True, exist_ok=True)
    jp = out_dir / f"{slug}_knowledge_package.json"
    jp.write_text(pkg.model_dump_json(indent=2), encoding="utf-8")
    mp = out_dir / f"{slug}_implementation_prompt.md"
    mp.write_text(pkg.implementation_specification.to_prompt(slug), encoding="utf-8")
    print(f"\nSaved JSON: {jp}")
    print(f"Saved prompt: {mp}")


if __name__ == "__main__":
    main()
