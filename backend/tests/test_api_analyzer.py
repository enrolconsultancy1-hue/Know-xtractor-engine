"""Tests for API discovery."""

from app.analyzers.api_analyzer import ApiAnalyzer
from app.analyzers.inventory import FileInventory
from app.analyzers.source_graph import SourceGraph


def test_extracts_fastapi_routes(sample_py_project):
    files = FileInventory(str(sample_py_project)).scan()
    spec = ApiAnalyzer().analyze(str(sample_py_project), files, SourceGraph(), {})
    methods = {(e.method, e.path) for e in spec.endpoints}
    assert ("get", "/users") in methods
    assert ("post", "/users") in methods


def test_flask_routes(tmp_path):
    (tmp_path / "app.py").write_text(
        "from flask import Flask\n"
        "app = Flask(__name__)\n\n"
        "@app.route('/hello')\n"
        "def hello():\n"
        "    return 'hi'\n",
        encoding="utf-8",
    )
    files = FileInventory(str(tmp_path)).scan()
    spec = ApiAnalyzer().analyze(str(tmp_path), files, SourceGraph(), {})
    paths = {e.path for e in spec.endpoints}
    assert "/hello" in paths


def test_router_prefix_resolution(tmp_path):
    (tmp_path / "routers").mkdir()
    (tmp_path / "routers" / "users.py").write_text(
        "from fastapi import APIRouter\n"
        "router = APIRouter(prefix='/users')\n\n"
        "@router.get('/me')\n"
        "def me():\n"
        "    return {}\n",
        encoding="utf-8",
    )
    (tmp_path / "main.py").write_text(
        "from fastapi import FastAPI\n"
        "from routers import users\n"
        "app = FastAPI()\n"
        "app.include_router(users.router, prefix='/api/v1')\n",
        encoding="utf-8",
    )
    files = FileInventory(str(tmp_path)).scan()
    spec = ApiAnalyzer().analyze(str(tmp_path), files, SourceGraph(), {})
    paths = {e.path for e in spec.endpoints}
    assert "/api/v1/users/me" in paths
