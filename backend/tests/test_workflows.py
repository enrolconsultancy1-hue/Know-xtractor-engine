"""Tests for workflow discovery."""

from app.analyzers.api_analyzer import ApiAnalyzer
from app.analyzers.inventory import FileInventory
from app.analyzers.python import PythonAnalyzer
from app.analyzers.source_graph import SourceGraph
from app.extractors.workflows import WorkflowExtractor


def test_api_workflows(sample_py_project):
    files = FileInventory(str(sample_py_project)).scan()
    graph = SourceGraph()
    PythonAnalyzer().analyze(str(sample_py_project), files, graph, {})
    api = ApiAnalyzer().analyze(str(sample_py_project), files, graph, {})
    workflows = WorkflowExtractor(graph, api).extract()
    names = {w.name for w in workflows}
    assert any("GET /users" in n for n in names)
    assert any("POST /users" in n for n in names)
    assert all(w.steps for w in workflows)
