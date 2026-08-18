"""Tests for the knowledge package, reconstruction, and implementation spec."""

from app.analyzers.api_analyzer import ApiAnalyzer
from app.analyzers.data_analyzer import DataAnalyzer
from app.analyzers.inventory import FileInventory
from app.analyzers.languages import LanguageDetector
from app.analyzers.python import PythonAnalyzer
from app.analyzers.source_graph import SourceGraph
from app.architecture.discovery import ArchitectureDiscoverer
from app.domain.sprint import EvolutionTimeline
from app.extractors.components import ComponentExtractor
from app.extractors.workflows import WorkflowExtractor
from app.services.knowledge_extractor import assemble_knowledge, build_implementation_spec


def _analyze(sample_py_project):
    root = str(sample_py_project)
    files = FileInventory(root).scan()
    graph = SourceGraph()
    PythonAnalyzer().analyze(root, files, graph, {})
    stack = LanguageDetector().analyze(root, files, graph, {})
    api = ApiAnalyzer().analyze(root, files, graph, {})
    data = DataAnalyzer().analyze(root, files, graph, {})
    components = ComponentExtractor(graph).extract()
    workflows = WorkflowExtractor(graph, api).extract()
    arch = ArchitectureDiscoverer(graph, components, stack, api).discover()
    return files, graph, stack, api, data, components, workflows, arch


def _assemble(sample_py_project):
    files, graph, stack, api, data, components, workflows, arch = _analyze(sample_py_project)
    pkg = assemble_knowledge(
        "sample", "https://example.com/sample.git", stack, arch,
        components, workflows, data, api, {}, [], {}, EvolutionTimeline(), [],
    )
    return pkg


def test_assemble_knowledge_package(sample_py_project):
    pkg = _assemble(sample_py_project)
    stats = pkg.stats()
    assert stats["component_count"] > 0
    assert stats["api_count"] >= 2
    assert stats["entity_count"] == 2
    assert pkg.architecture.primary_pattern
    assert pkg.facts  # facts/inferences present


def test_implementation_spec_and_prompt(sample_py_project):
    pkg = _assemble(sample_py_project)
    spec = build_implementation_spec(pkg)
    prompt = spec.to_prompt("sample")
    assert "IMPLEMENT THIS ARCHITECTURE" in prompt
    assert spec.implementation_order
    assert spec.acceptance_criteria


def test_reconstruction_preserves_knowledge(sample_py_project):
    pkg = _assemble(sample_py_project)
    rec = pkg.reconstructed_architecture
    assert rec.essential_capabilities
    assert rec.technology_bindings
    # Knowledge layer independent of technology: domain model retained.
    assert any("User" in d for d in rec.domain_model)
