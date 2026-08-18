"""Tests for DB/infra fingerprinting and env-contract extraction (goal #4)."""

from app.analyzers.config_analyzer import ConfigAnalyzer
from app.analyzers.inventory import FileInventory
from app.analyzers.languages import LanguageDetector
from app.analyzers.source_graph import SourceGraph


def test_database_detected_from_settings_source(tmp_path):
    (tmp_path / "settings.py").write_text(
        "DATABASES = {'default': {'ENGINE': 'django.db.backends.postgresql'}}\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("print('hi')\n", encoding="utf-8")
    files = FileInventory(str(tmp_path)).scan()
    stack = LanguageDetector().analyze(str(tmp_path), files, SourceGraph(), {})
    assert "PostgreSQL" in {t.name for t in stack.databases}


def test_broker_and_cache_detected_from_source(tmp_path):
    (tmp_path / "tasks.py").write_text(
        "import pika\nimport redis\nfrom celery import Celery\n", encoding="utf-8")
    (tmp_path / "main.py").write_text("x = 1\n", encoding="utf-8")
    files = FileInventory(str(tmp_path)).scan()
    stack = LanguageDetector().analyze(str(tmp_path), files, SourceGraph(), {})
    dbs = {t.name for t in stack.databases}
    infra = {t.name for t in stack.infrastructure}
    assert "Redis" in dbs
    assert "RabbitMQ" in infra
    assert "Celery" in infra


def test_comment_only_db_mention_is_ignored(tmp_path):
    (tmp_path / "util.py").write_text(
        "# MongoDB is not supported here, only in a comment\nvalue = 1\n", encoding="utf-8")
    (tmp_path / "main.py").write_text("x = 1\n", encoding="utf-8")
    files = FileInventory(str(tmp_path)).scan()
    stack = LanguageDetector().analyze(str(tmp_path), files, SourceGraph(), {})
    assert "MongoDB" not in {t.name for t in stack.databases}


def test_real_db_usage_still_detected(tmp_path):
    (tmp_path / "db.py").write_text(
        "import pymongo\nclient = pymongo.MongoClient()\n", encoding="utf-8")
    (tmp_path / "main.py").write_text("x = 1\n", encoding="utf-8")
    files = FileInventory(str(tmp_path)).scan()
    stack = LanguageDetector().analyze(str(tmp_path), files, SourceGraph(), {})
    assert "MongoDB" in {t.name for t in stack.databases}


def test_env_vars_extracted_from_python_source(tmp_path):
    (tmp_path / "config.py").write_text(
        "import os\nDB_URL = os.getenv('DB_URL')\nSECRET = os.environ['SECRET_KEY']\n"
        "NAME = os.environ.get('APP_NAME')\n", encoding="utf-8")
    files = FileInventory(str(tmp_path)).scan()
    result = ConfigAnalyzer().analyze(str(tmp_path), files, SourceGraph(), {})
    assert "DB_URL" in result["env_vars"]
    assert "SECRET_KEY" in result["env_vars"]
    assert "APP_NAME" in result["env_vars"]


def test_env_vars_extracted_from_js_source(tmp_path):
    (tmp_path / "index.js").write_text(
        "const a = process.env.API_BASE;\nconst b = process.env['API_TOKEN'];\n", encoding="utf-8")
    files = FileInventory(str(tmp_path)).scan()
    result = ConfigAnalyzer().analyze(str(tmp_path), files, SourceGraph(), {})
    assert "API_BASE" in result["env_vars"]
    assert "API_TOKEN" in result["env_vars"]


def test_config_keys_still_recorded(tmp_path):
    (tmp_path / ".env").write_text("DEBUG=true\nDATABASE_URL=postgres://x\n", encoding="utf-8")
    files = FileInventory(str(tmp_path)).scan()
    result = ConfigAnalyzer().analyze(str(tmp_path), files, SourceGraph(), {})
    assert "DEBUG" in result["keys"]
    # DATABASE_URL is classified secret and its value never persisted.
    assert "DATABASE_URL" in result["secret_required"]
    assert all("postgres" not in str(v) for v in result["secrets_found"])
