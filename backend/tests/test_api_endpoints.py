"""API endpoint smoke tests using FastAPI TestClient."""


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_root(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["app"] == "KNOX"


def test_create_and_list_projects(client):
    resp = client.post("/api/projects", json={"repository_url": "https://github.com/example/repo.git"})
    assert resp.status_code == 201
    project_id = resp.json()["id"]
    assert project_id > 0

    listing = client.get("/api/projects")
    assert listing.status_code == 200
    assert any(p["id"] == project_id for p in listing.json())


def test_analyze_requires_valid_url(client):
    resp = client.post("/api/projects", json={"repository_url": "https://github.com/example/repo.git"})
    project_id = resp.json()["id"]
    # Analysis starts asynchronously; a 202 is returned.
    resp2 = client.post(f"/api/projects/{project_id}/analyze", json={"branch": "main"})
    assert resp2.status_code == 202
    assert "analysis_id" in resp2.json()


def test_security_response_headers(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("X-XSS-Protection") == "1; mode=block"
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "geolocation=()" in resp.headers.get("Permissions-Policy", "")
    assert "X-Request-ID" in resp.headers


def test_analysis_stream_not_found(client):
    resp = client.get("/api/analysis/999999/stream")
    assert resp.status_code == 404


def test_analysis_stream_completed(client):
    from app.services.runner import _runs

    resp_proj = client.post("/api/projects", json={"repository_url": "https://github.com/example/test.git"})
    assert resp_proj.status_code == 201
    proj_id = resp_proj.json()["id"]

    resp_an = client.post(f"/api/projects/{proj_id}/analyze", json={"branch": "main"})
    assert resp_an.status_code == 202
    run_id = resp_an.json()["analysis_id"]

    _runs[run_id] = {
        "status": "done",
        "stage": "completed",
        "progress": 1.0,
        "events": [{"stage": "completed", "pct": 1.0, "message": "All done"}],
        "summary": {"files": 10},
    }

    resp = client.get(f"/api/analysis/{run_id}/stream")
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("Content-Type", "")
    content = resp.text
    assert "event: progress" in content or "event: status" in content
    assert "event: done" in content



