"""Pytest fixtures: build small fixture repositories for testing analyzers."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

# Point KNOX runtime dirs at a temp location *before* any app module import.
_TMP = Path(os.environ.get("TEMP", ".")) / "knox_test_data"
_TMP.mkdir(parents=True, exist_ok=True)
os.environ["KNOX_DATA_DIR"] = str(_TMP / "data")
os.environ["KNOX_WORKSPACE_DIR"] = str(_TMP / "workspace")
os.environ["KNOX_PACKAGES_DIR"] = str(_TMP / "packages")
os.environ["KNOX_EXPORTS_DIR"] = str(_TMP / "exports")

# Reset any cached settings singleton so the env vars take effect.
try:
    import app.core.config as _cfg

    _cfg._settings = None
except Exception:
    pass


@pytest.fixture
def sample_py_project(tmp_path: Path) -> Path:
    """Create a small FastAPI + SQLAlchemy project on disk."""
    root = tmp_path / "sample"
    (root / "app").mkdir(parents=True)
    (root / "app" / "models.py").write_text(
        "from sqlalchemy import Column, Integer, String, ForeignKey\n"
        "from sqlalchemy.orm import declarative_base\n\n"
        "Base = declarative_base()\n\n"
        "class User(Base):\n"
        "    __tablename__ = 'users'\n"
        "    id = Column(Integer, primary_key=True)\n"
        "    email = Column(String, nullable=False)\n\n"
        "class Project(Base):\n"
        "    __tablename__ = 'projects'\n"
        "    id = Column(Integer, primary_key=True)\n"
        "    user_id = Column(Integer, ForeignKey('users.id'))\n",
        encoding="utf-8",
    )
    (root / "app" / "services.py").write_text(
        "class UserService:\n"
        "    \"\"\"Manages users.\"\"\"\n"
        "    def create_user(self, email: str):\n"
        "        return self._repo.save(email)\n",
        encoding="utf-8",
    )
    (root / "app" / "main.py").write_text(
        "from fastapi import FastAPI\n"
        "from app.services import UserService\n\n"
        "app = FastAPI()\n"
        "service = UserService()\n\n"
        "@app.get('/users')\n"
        "def list_users():\n"
        "    return service.list()\n\n"
        "@app.post('/users')\n"
        "def create_user():\n"
        "    return service.create_user('a@b.c')\n",
        encoding="utf-8",
    )
    (root / "requirements.txt").write_text(
        "fastapi==0.115.0\nsqlalchemy==2.0.36\npydantic==2.10.0\n", encoding="utf-8"
    )
    (root / ".gitignore").write_text("__pycache__/\n*.pyc\n", encoding="utf-8")
    (root / "README.md").write_text(
        "# Sample\nA FastAPI + SQLAlchemy sample service.\n", encoding="utf-8"
    )
    (root / "tests").mkdir()
    (root / "tests" / "test_services.py").write_text(
        "import pytest\n\n"
        "def test_create_user():\n"
        "    assert True\n\n"
        "def test_list_users():\n"
        "    assert True\n",
        encoding="utf-8",
    )
    return root


@pytest.fixture
def git_project(tmp_path: Path) -> Path:
    """Create a repo with a few commits for sprint clustering tests."""
    root = tmp_path / "gitrepo"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=root, check=True)

    def commit(msg: str, filename: str) -> None:
        (root / filename).write_text(f"# {msg}\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(["git", "commit", "-q", "-m", msg], cwd=root, check=True)

    commit("Initial application skeleton", "main.py")
    commit("Introduce API layer with routes", "api.py")
    commit("Add database models and migration", "models.py")
    commit("Add authentication middleware", "auth.py")
    return root
