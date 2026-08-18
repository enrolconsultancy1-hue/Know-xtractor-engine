"""Tests for the prompt compiler (knowledge -> budgeted rebuild prompt)."""

from __future__ import annotations

from app.domain.api_model import ApiEndpoint, ApiSpec
from app.domain.common import Confidence
from app.domain.component import Component, ComponentType
from app.domain.data_model import DataColumn, DataEntity, DataModel
from app.domain.knowledge import KnowledgePackage
from app.domain.workflow import Workflow, WorkflowStep
from app.services.prompt_compiler import (
    _component_importance,
    compile_prompt,
    estimate_tokens,
    to_engineered_prompt,
)


def _component(name, ctype=ComponentType.MODULE, deps=(), consumers=(), layer="application"):
    return Component(
        id=name,
        name=name,
        type=ctype,
        purpose=f"purpose of {name}",
        dependencies=list(deps),
        consumers=list(consumers),
        architectural_layer=layer,
        confidence=Confidence(score=0.7),
    )


def _entity(name, ncols=3):
    return DataEntity(
        name=name,
        kind="table",
        columns=[DataColumn(name=f"col{i}", type="str") for i in range(ncols)],
    )


def _endpoint(method, path, handler):
    return ApiEndpoint(method=method, path=path, handler=handler, file=f"{path}.py", request_schema="Req", response_schema="Resp")


def _workflow(i):
    return Workflow(
        id=f"w{i}",
        name=f"workflow-{i}",
        entry_point=f"entry_{i}",
        confidence=Confidence(score=0.7),
        steps=[WorkflowStep(id=f"s{i}", name=f"step-{i}", kind="transform")],
    )


def _pkg(n_components=5, n_entities=3, n_endpoints=3, n_workflows=2):
    pkg = KnowledgePackage.new("demo", "https://github.com/a/b.git")
    pkg.components = [_component(f"component_{i}") for i in range(n_components)]
    pkg.data_model = DataModel(entities=[_entity(f"entity_{i}") for i in range(n_entities)])
    pkg.apis = ApiSpec(endpoints=[_endpoint("GET", f"/r{i}", f"h{i}") for i in range(n_endpoints)])
    pkg.workflows = [_workflow(i) for i in range(n_workflows)]
    return pkg


def test_estimate_tokens():
    assert estimate_tokens("") == 1
    assert estimate_tokens("1234") == 1
    assert estimate_tokens("12345") == 2  # ceil(5/4)


def test_component_importance_ranks_significant_types_first():
    leaf = _component("leaf_module")
    api = _component("orders_api", ComponentType.API_CONTROLLER, consumers=["router"])
    svc = _component("auth_service", ComponentType.SERVICE, deps=["db"], consumers=["api"])
    assert _component_importance(api, set()) > _component_importance(leaf, set())
    assert _component_importance(svc, set()) > _component_importance(leaf, set())
    assert _component_importance(svc, {"auth_service"}) > _component_importance(api, set())


def test_small_package_fits_without_chunks():
    compiled = compile_prompt(_pkg(), max_tokens=50000)
    assert compiled.main
    assert "IMPLEMENT THIS ARCHITECTURE" in compiled.main
    assert "Rebuild Instructions" in compiled.main
    assert compiled.truncated is False
    assert compiled.chunks == []
    assert compiled.total_tokens <= 50000


def test_large_package_truncates_to_chunks_but_keeps_summary():
    pkg = _pkg(n_components=300, n_entities=200, n_endpoints=300, n_workflows=150)
    compiled = compile_prompt(pkg, max_tokens=3000)
    assert compiled.truncated is True
    assert compiled.chunks  # detail pushed out
    # Main must remain self-contained and useful.
    assert "Rebuild Instructions" in compiled.main
    assert "Top " in compiled.main
    assert all(c.content for c in compiled.chunks)


def test_to_engineered_prompt_lists_chunks():
    pkg = _pkg(n_components=300, n_entities=200, n_endpoints=300, n_workflows=150)
    text = to_engineered_prompt(pkg, max_tokens=3000)
    assert "Rebuild Instructions" in text
    assert "Additional Detail Chunks" in text
    assert "components-" in text


def test_entity_line_renders_constraints():
    from app.domain.data_model import DataColumn
    from app.services.prompt_compiler import _render_entity_line

    e = DataEntity(
        name="User",
        kind="model",
        columns=[
            DataColumn(name="id", type="integer", primary_key=True, nullable=False),
            DataColumn(name="email", type="string", nullable=False),
            DataColumn(name="name", type="string", default="''"),
        ],
    )
    line = _render_entity_line(e)
    assert "id:integer[pk,not-null]" in line
    assert "email:string[not-null]" in line
    assert "name:string[default='']" in line
