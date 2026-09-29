"""Tests for projects API endpoints: get, reanalyze, cancel, delete, and 404s."""

from __future__ import annotations

from app.domain.knowledge import KnowledgePackage, LogicCaptureBody, LogicCaptureSection
from app.services.exporter import to_markdown


def test_project_crud_lifecycle(client):
    # 404 for non-existent project
    assert client.get("/api/projects/99999").status_code == 404
    assert client.post("/api/projects/99999/analyze", json={"branch": "main"}).status_code == 404
    assert client.post("/api/projects/99999/reanalyze", json={"branch": "main"}).status_code == 404
    assert client.delete("/api/projects/99999").status_code == 404

    # Create project
    create_resp = client.post("/api/projects", json={"repository_url": "https://github.com/example/lifecycle.git"})
    assert create_resp.status_code == 201
    pid = create_resp.json()["id"]

    # Get project details
    get_resp = client.get(f"/api/projects/{pid}")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["id"] == pid
    assert data["repository_url"] == "https://github.com/example/lifecycle.git"

    # Analyze and Reanalyze
    an_resp = client.post(f"/api/projects/{pid}/analyze", json={"branch": "main"})
    assert an_resp.status_code == 202
    assert "analysis_id" in an_resp.json()

    rean_resp = client.post(f"/api/projects/{pid}/reanalyze", json={"branch": "main"})
    assert rean_resp.status_code == 202
    assert "analysis_id" in rean_resp.json()

    # Cancel active runs
    cancel_resp = client.post(f"/api/projects/{pid}/cancel")
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelled"

    # Delete project (cascades runs)
    del_resp = client.delete(f"/api/projects/{pid}")
    assert del_resp.status_code == 204

    # Verify deleted
    assert client.get(f"/api/projects/{pid}").status_code == 404


def test_exporter_markdown_logic_capture_and_risks():
    pkg = KnowledgePackage(
        metadata={"repository": "test-repo"},
        risks=["Security vulnerability in old dep", "Scalability limit"],
        logic_capture=LogicCaptureSection(
            captured=[
                LogicCaptureBody(
                    name="calculate_tax",
                    kind="function",
                    path="tax.py",
                    language="python",
                    line=10,
                    body="def calculate_tax(x): return x * 0.1",
                )
            ]
        ),
    )
    md = to_markdown(pkg)
    assert "## Logic Capture (source-of-record)" in md
    assert "calculate_tax" in md
    assert "## Risks" in md
    assert "Security vulnerability in old dep" in md
