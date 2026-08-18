"""End-to-end pipeline test on a fixture repository."""

from app.services.pipeline import AnalysisPipeline, PipelineContext


def test_pipeline_end_to_end(sample_py_project):
    ctx = PipelineContext(repository="sample", repo_path=str(sample_py_project))
    stages: list[str] = []
    pkg = AnalysisPipeline().run(ctx, lambda s, p, m: stages.append(s))
    assert pkg is not None
    assert ctx.stack.languages
    assert ctx.components
    assert ctx.workflows
    assert ctx.apis.endpoints
    assert "done" in stages
    assert pkg.facts


def test_pipeline_is_resilient_to_bad_files(tmp_path):
    (tmp_path / "good.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    (tmp_path / "bad.py").write_text("def broken(:\n", encoding="utf-8")
    ctx = PipelineContext(repository="resilient", repo_path=str(tmp_path))
    pkg = AnalysisPipeline().run(ctx)
    assert pkg is not None
    # One malformed file must not destroy the analysis.
    assert ctx.graph.error_count() >= 1
