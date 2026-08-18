"""Tests for call-graph + data-flow analysis."""

from __future__ import annotations

from app.analyzers.callgraph import CallGraph, CallKind, classify_call
from app.analyzers.source_graph import SourceGraph, SourceModule, Symbol, SymbolKind
from app.domain.api_model import ApiEndpoint, ApiSpec
from app.domain.common import Confidence
from app.extractors.workflows import WorkflowExtractor


def _sym(name, path, calls=(), kind=SymbolKind.FUNCTION):
    return Symbol(name=name, kind=kind, path=path, calls=list(calls))


def _graph(*modules):
    g = SourceGraph()
    for m in modules:
        g.add(m)
    return g


def test_classify_call():
    assert classify_call("session.query") is CallKind.PERSISTENCE
    assert classify_call("Model.objects.filter") is CallKind.PERSISTENCE
    assert classify_call("cursor.execute") is CallKind.PERSISTENCE
    assert classify_call("requests.get") is CallKind.EXTERNAL
    assert classify_call("httpx.post") is CallKind.EXTERNAL
    assert classify_call("fetch") is CallKind.EXTERNAL
    assert classify_call("task.delay") is CallKind.QUEUE
    assert classify_call("celery_app.send_task") is CallKind.QUEUE
    assert classify_call("redis_client.get") is CallKind.CACHE
    assert classify_call("util.format") is CallKind.UNKNOWN


def test_classify_call_cross_language():
    # Go / Java / C# / Ruby / PHP persistence + external markers.
    assert classify_call("db.Query") is CallKind.PERSISTENCE
    assert classify_call("sql.Open") is CallKind.PERSISTENCE
    assert classify_call("gorm.DB.Find") is CallKind.PERSISTENCE
    assert classify_call("jdbcTemplate.query") is CallKind.PERSISTENCE
    assert classify_call("repository.findByName") is CallKind.PERSISTENCE
    assert classify_call("http.Get") is CallKind.EXTERNAL
    assert classify_call("httpClient.GetAsync") is CallKind.EXTERNAL
    assert classify_call("restTemplate.getForObject") is CallKind.EXTERNAL
    assert classify_call("kafka.Publish") is CallKind.QUEUE
    assert classify_call("redis.Get") is CallKind.CACHE


def test_trace_reaches_persistence_through_internal_calls():
    g = _graph(
        SourceModule(path="api.py", language="python", symbols=[
            _sym("list_items", "api.py", calls=["item_service.list_all"]),
        ]),
        SourceModule(path="service.py", language="python", symbols=[
            _sym("list_all", "service.py", calls=["session.query", "format_item"]),
        ]),
    )
    cg = CallGraph(g)
    trace = cg.trace("api.py:list_items")
    labels = [t[0] for t in trace]
    kinds = {t[1] for t in trace}
    # Internal call is resolved and traversed; persistence marker appears.
    assert "item_service.list_all" in labels
    assert CallKind.PERSISTENCE in kinds
    assert cg.reachable_kinds("api.py:list_items") == {CallKind.PERSISTENCE}


def test_trace_is_cycle_safe():
    g = _graph(
        SourceModule(path="a.py", language="python", symbols=[
            _sym("a_fn", "a.py", calls=["b_fn"]),
        ]),
        SourceModule(path="b.py", language="python", symbols=[
            _sym("b_fn", "b.py", calls=["a_fn"]),
        ]),
    )
    cg = CallGraph(g)
    trace = cg.trace("a.py:a_fn", max_depth=6, max_nodes=20)
    assert len(trace) <= 20  # terminates despite the cycle


def test_workflow_extractor_marks_persistence_steps():
    g = _graph(
        SourceModule(path="api.py", language="python", symbols=[
            _sym("create_order", "api.py", calls=["order_service.create"]),
        ]),
        SourceModule(path="service.py", language="python", symbols=[
            _sym("create", "service.py", calls=["session.commit"]),
        ]),
    )
    api = ApiSpec(endpoints=[
        ApiEndpoint(method="POST", path="/orders", handler="create_order", file="api.py",
                    confidence=Confidence(score=0.85)),
    ])
    cg = CallGraph(g)
    workflows = WorkflowExtractor(g, api, cg).extract()
    assert workflows
    steps = workflows[0].steps
    kinds = [s.kind for s in steps]
    assert "persistence" in kinds
    assert any(s.name == "session.commit" for s in steps)
