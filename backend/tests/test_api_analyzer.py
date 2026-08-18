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


def test_fastapi_request_response_type_linking(tmp_path):
    (tmp_path / "main.py").write_text(
        "from fastapi import FastAPI, Depends\n"
        "from pydantic import BaseModel\n\n"
        "app = FastAPI()\n\n"
        "class UserCreate(BaseModel):\n"
        "    email: str\n\n"
        "class User(BaseModel):\n"
        "    id: int\n"
        "    email: str\n\n"
        "@app.post('/users')\n"
        "def create_user(user: UserCreate) -> User:\n"
        "    return User(id=1, email=user.email)\n\n"
        "@app.get('/users')\n"
        "def list_users(limit: int = 10) -> list[User]:\n"
        "    return []\n",
        encoding="utf-8",
    )
    files = FileInventory(str(tmp_path)).scan()
    spec = ApiAnalyzer().analyze(str(tmp_path), files, SourceGraph(), {})
    by_key = {(e.method, e.path): e for e in spec.endpoints}
    post = by_key[("post", "/users")]
    assert post.request_schema == "UserCreate"
    assert post.response_schema == "User"
    get = by_key[("get", "/users")]
    assert get.request_schema is None  # scalar query param, not a body schema
    assert get.response_schema == "list[User]"


def test_django_drf_serializer_linking(tmp_path):
    (tmp_path / "urls.py").write_text(
        "from django.urls import path\n"
        "from .views import UserViewSet\n\n"
        "urlpatterns = [\n"
        "    path('users/', UserViewSet.as_view()),\n"
        "]\n",
        encoding="utf-8",
    )
    (tmp_path / "views.py").write_text(
        "from rest_framework import viewsets\n"
        "from .serializers import UserSerializer\n\n"
        "class UserViewSet(viewsets.ModelViewSet):\n"
        "    serializer_class = UserSerializer\n",
        encoding="utf-8",
    )
    files = FileInventory(str(tmp_path)).scan()
    spec = ApiAnalyzer().analyze(str(tmp_path), files, SourceGraph(), {})
    ep = next(e for e in spec.endpoints if e.handler == "UserViewSet.as_view")
    assert ep.request_schema == "UserSerializer"
    assert ep.response_schema == "UserSerializer"
