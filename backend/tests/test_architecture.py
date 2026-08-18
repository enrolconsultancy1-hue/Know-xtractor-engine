"""Tests for architecture pattern discovery, incl. the microservices gate."""

from app.analyzers.source_graph import SourceGraph, SourceModule
from app.architecture.discovery import ArchitectureDiscoverer
from app.domain.api_model import ApiSpec
from app.domain.technology import TechnologyStack


def _report(paths: list[str]):
    graph = SourceGraph()
    for p in paths:
        graph.add(SourceModule(path=p, language="python"))
    return ArchitectureDiscoverer(graph, [], TechnologyStack(), ApiSpec()).discover()


def test_monolith_with_background_jobs_is_not_microservices():
    # Entry points live under examples/tests; background code exists but there
    # is only a single "src" service root -> must NOT be classified microservices.
    report = _report([
        "src/flask/app.py",
        "src/flask/core.py",
        "examples/celery/make_celery.py",
        "tests/test_app.py",
    ])
    names = {p.name for p in report.patterns}
    assert "Microservices" not in names


def test_multiple_service_roots_is_microservices():
    report = _report([
        "service-a/main.py",
        "service-b/main.py",
        "service-a/api.py",
        "service-b/worker.py",
    ])
    names = {p.name for p in report.patterns}
    assert "Microservices" in names
