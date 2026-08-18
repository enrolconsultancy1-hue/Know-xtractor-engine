"""Tests for hardcoded-secret detection (locations only, never values)."""

from app.analyzers.inventory import FileInventory
from app.analyzers.secret_scanner import SecretScanner, scan_source
from app.analyzers.source_graph import SourceGraph


def test_detects_aws_access_key():
    findings = scan_source("AWS_KEY = 'AKIAIOSFODNN7EXAMPLE'", "config.py")
    assert findings and findings[0]["category"] == "aws_access_key"
    assert findings[0]["confidence"] == 0.9


def test_detects_private_key_block():
    findings = scan_source("key = '''-----BEGIN RSA PRIVATE KEY-----'''", "x.py")
    assert any(f["category"] == "private_key" for f in findings)


def test_detects_hardcoded_password():
    findings = scan_source('password = "hunter2"', "x.py")
    assert findings
    assert findings[0]["key"] == "password"
    assert findings[0]["confidence"] == 0.7


def test_detects_connection_string():
    findings = scan_source('DB_URL = "postgres://user:hunter2@localhost/db"', "x.py")
    assert any(f["category"] == "connection_string" for f in findings)


def test_skips_env_read():
    assert scan_source('password = os.environ["PASSWORD"]', "x.py") == []
    assert scan_source('api_key = os.getenv("API_KEY")', "x.py") == []


def test_skips_placeholder_values():
    assert scan_source('password = "password"', "x.py") == []
    assert scan_source('secret = "changeme"', "x.py") == []


def test_skips_comment_only():
    assert scan_source('# password = "hunter2"', "x.py") == []


def test_skips_sql_template_placeholder():
    # "password" inside set_password / format-string templates is not a secret.
    assert scan_source("set_password = 'ALTER USER x IDENTIFIED BY \"%(password)s\"'", "x.py") == []


def test_values_never_captured():
    findings = scan_source('api_key = "super-secret-value-123"', "x.py")
    assert findings
    f = findings[0]
    assert "value" not in f
    assert "super-secret-value-123" not in str(f)
    assert f["line"] == 1
    assert f["file"] == "x.py"


def test_scanner_end_to_end(tmp_path):
    (tmp_path / "settings.py").write_text("db_password = 'hunter2'\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("print('hi')\n", encoding="utf-8")
    files = FileInventory(str(tmp_path)).scan()
    findings = SecretScanner().analyze(str(tmp_path), files, SourceGraph(), {})
    assert any(f["key"] == "db_password" for f in findings)
    # No secret value ever appears in the output.
    assert "hunter2" not in str(findings)


def test_pipeline_surfaces_hardcoded_secrets(sample_py_project):
    from app.services.pipeline import AnalysisPipeline, PipelineContext

    (sample_py_project / "app" / "config.py").write_text(
        "db_password = 'hunter2'\n", encoding="utf-8")
    ctx = PipelineContext(repository="sample", repo_path=str(sample_py_project))
    pkg = AnalysisPipeline().run(ctx)
    assert any("hardcoded secret" in s.lower() for s in pkg.security)
    assert any(f.category == "security" and "hardcoded secret" in f.fact for f in pkg.facts)
    # The secret value never leaks into the knowledge package.
    assert "hunter2" not in str(pkg.configuration)
    assert "hunter2" not in str(pkg.facts)
    assert "hunter2" not in str(pkg.security)
