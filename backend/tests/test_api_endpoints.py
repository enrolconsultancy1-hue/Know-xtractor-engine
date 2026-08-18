"""API endpoint smoke tests using FastAPI TestClient."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_root():
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["app"] == "KNOX"


def test_create_and_list_projects():
    resp = client.post("/api/projects", json={"repository_url": "https://github.com/example/repo.git"})
    assert resp.status_code == 201
    project_id = resp.json()["id"]
    assert project_id > 0

    listing = client.get("/api/projects")
    assert listing.status_code == 200
    assert any(p["id"] == project_id for p in listing.json())


def test_analyze_requires_valid_url():
    resp = client.post("/api/projects", json={"repository_url": "https://github.com/example/repo.git"})
    project_id = resp.json()["id"]
    # Analysis starts asynchronously; a 202 is returned.
    resp2 = client.post(f"/api/projects/{project_id}/analyze", json={"branch": "main"})
    assert resp2.status_code == 202
    assert "analysis_id" in resp2.json()
