"""Tests for knowledge, architecture, and analysis API endpoints."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from app.domain.common import Confidence
from app.domain.component import Component, ComponentType
from app.domain.knowledge import KnowledgePackage
from app.domain.workflow import Workflow, WorkflowStep
from app.knowledge.graph import build_knowledge_graph


def _make_sample_pkg() -> KnowledgePackage:
    return KnowledgePackage(
        metadata={"repository": "test-repo", "commit": "abc1234"},
        components=[
            Component(
                id="auth_service",
                name="AuthService",
                type=ComponentType.SERVICE,
                purpose="Handles auth",
                confidence=Confidence(score=0.9),
            ),
            Component(
                id="api_gateway",
                name="ApiGateway",
                type=ComponentType.API_CONTROLLER,
                purpose="Routing requests",
                confidence=Confidence(score=0.95),
            ),
        ],
        workflows=[
            Workflow(
                id="login_flow",
                name="Login Flow",
                entry_point="step_1",
                confidence=Confidence(score=0.85),
                steps=[
                    WorkflowStep(id="step_1", name="Verify Credentials"),
                    WorkflowStep(id="step_2", name="Issue Token", dependencies=["step_1"]),
                ],
            )
        ],
    )


def test_build_knowledge_graph():
    pkg = _make_sample_pkg()
    g = build_knowledge_graph(pkg)
    assert "nodes" in g
    assert "edges" in g
    node_ids = {n["id"] for n in g["nodes"]}
    assert "auth_service" in node_ids
    assert "api_gateway" in node_ids
    assert "login_flow" in node_ids


def test_knowledge_endpoints_404_and_409(client):
    # Non-existent project
    resp = client.get("/api/projects/9999/knowledge")
    assert resp.status_code == 404

    # Create project but mock load_package returning None
    created = client.post("/api/projects", json={"repository_url": "https://github.com/example/pkg-test.git"})
    assert created.status_code == 201
    pid = created.json()["id"]

    with patch("app.api.knowledge.load_package", return_value=None):
        resp = client.get(f"/api/projects/{pid}/knowledge")
        assert resp.status_code == 409


def test_knowledge_endpoints_with_package(client):
    created = client.post("/api/projects", json={"repository_url": "https://github.com/example/pkg-ok.git"})
    pid = created.json()["id"]

    pkg = _make_sample_pkg()
    pkg_dict = pkg.model_dump(mode="json")

    with patch("app.api.knowledge.load_package", return_value=pkg_dict):
        assert client.get(f"/api/projects/{pid}/knowledge").status_code == 200
        assert client.get(f"/api/projects/{pid}/architecture").status_code == 200
        assert client.get(f"/api/projects/{pid}/components").status_code == 200
        assert client.get(f"/api/projects/{pid}/workflows").status_code == 200
        assert client.get(f"/api/projects/{pid}/technologies").status_code == 200
        assert client.get(f"/api/projects/{pid}/sprints").status_code == 200

        graph_resp = client.get(f"/api/projects/{pid}/graph")
        assert graph_resp.status_code == 200
        assert "nodes" in graph_resp.json()


def test_export_endpoints(client):
    created = client.post("/api/projects", json={"repository_url": "https://github.com/example/export-test.git"})
    pid = created.json()["id"]

    pkg = _make_sample_pkg()
    pkg_dict = pkg.model_dump(mode="json")

    with patch("app.api.architecture.load_package", return_value=pkg_dict):
        # Markdown export
        resp_md = client.post(f"/api/projects/{pid}/export?fmt=markdown")
        assert resp_md.status_code == 200
        assert resp_md.json()["media_type"] == "text/markdown"

        # JSON export
        resp_json = client.post(f"/api/projects/{pid}/export?fmt=json")
        assert resp_json.status_code == 200
        assert resp_json.json()["media_type"] == "application/json"

        # YAML export
        resp_yaml = client.post(f"/api/projects/{pid}/export?fmt=yaml")
        assert resp_yaml.status_code == 200
        assert resp_yaml.json()["media_type"] == "application/yaml"


def test_analysis_endpoints(client):
    # Non-existent analysis
    resp = client.get("/api/analysis/9999")
    assert resp.status_code == 404

    resp_events = client.get("/api/analysis/9999/events")
    assert resp_events.status_code == 404

    # Trigger analysis on project to get a valid analysis_id
    created = client.post("/api/projects", json={"repository_url": "https://github.com/example/run-test.git"})
    pid = created.json()["id"]
    analyze_resp = client.post(f"/api/projects/{pid}/analyze", json={"branch": "main"})
    aid = analyze_resp.json()["analysis_id"]

    resp = client.get(f"/api/analysis/{aid}")
    assert resp.status_code == 200
    assert resp.json()["id"] == aid

    events_resp = client.get(f"/api/analysis/{aid}/events")
    assert events_resp.status_code == 200
    assert "status" in events_resp.json()


def test_customize_and_prompt_endpoints(client, tmp_path: Path):
    created = client.post("/api/projects", json={"repository_url": "https://github.com/example/arch-test.git"})
    pid = created.json()["id"]

    pkg = _make_sample_pkg()
    pkg_dict = pkg.model_dump(mode="json")
    dummy_pkg_path = tmp_path / f"project_{pid}.json"

    with patch("app.api.architecture.load_package", return_value=pkg_dict), \
         patch("app.services.runner.package_path", return_value=dummy_pkg_path):

        # Customize architecture
        cust_resp = client.post(
            f"/api/projects/{pid}/architecture/customize",
            json={"backend_technology": "Go", "database": "PostgreSQL"},
        )
        assert cust_resp.status_code == 200
        assert "reconstructed_architecture" in cust_resp.json()
        assert "implementation_specification" in cust_resp.json()

        # Implementation prompt with customization request
        prompt_resp = client.post(
            f"/api/projects/{pid}/implementation-prompt",
            json={"frontend_technology": "Vue"},
        )
        assert prompt_resp.status_code == 200
        assert "prompt" in prompt_resp.json()

        # Implementation prompt without customization request
        prompt_resp2 = client.post(f"/api/projects/{pid}/implementation-prompt", json={})
        assert prompt_resp2.status_code == 200
        assert "prompt" in prompt_resp2.json()

