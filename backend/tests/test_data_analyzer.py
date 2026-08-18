"""Tests for data model discovery."""

from app.analyzers.data_analyzer import DataAnalyzer
from app.analyzers.inventory import FileInventory
from app.analyzers.source_graph import SourceGraph


def test_extracts_sqlalchemy_models(sample_py_project):
    files = FileInventory(str(sample_py_project)).scan()
    model = DataAnalyzer().analyze(str(sample_py_project), files, SourceGraph(), {})
    names = {e.name for e in model.entities}
    assert "User" in names
    assert "Project" in names
    user = next(e for e in model.entities if e.name == "User")
    cols = {c.name for c in user.columns}
    assert "id" in cols
    assert "email" in cols
    assert any(c.primary_key for c in user.columns)


def test_extracts_relationship(sample_py_project):
    files = FileInventory(str(sample_py_project)).scan()
    model = DataAnalyzer().analyze(str(sample_py_project), files, SourceGraph(), {})
    rels = {(r.source, r.target) for r in model.relationships}
    assert ("Project", "User") in rels


def test_alembic_migration_parsing(tmp_path):
    (tmp_path / "migration.py").write_text(
        "op.create_table(\n"
        "    'users',\n"
        "    sa.Column('id', sa.Integer(), primary_key=True),\n"
        "    sa.Column('email', sa.String(length=255), nullable=False),\n"
        ")\n",
        encoding="utf-8")
    files = FileInventory(str(tmp_path)).scan()
    model = DataAnalyzer().analyze(str(tmp_path), files, SourceGraph(), {})
    names = {e.name for e in model.entities}
    assert "users" in names
    users = next(e for e in model.entities if e.name == "users")
    assert {c.name for c in users.columns} >= {"id", "email"}
    assert users.source_kind == "alembic"


def test_django_migration_parsing(tmp_path):
    (tmp_path / "0001_initial.py").write_text(
        "migrations.CreateModel(\n"
        "    name='User',\n"
        "    fields=[\n"
        "        ('id', models.AutoField(primary_key=True)),\n"
        "        ('email', models.EmailField()),\n"
        "    ],\n"
        ")\n",
        encoding="utf-8")
    files = FileInventory(str(tmp_path)).scan()
    model = DataAnalyzer().analyze(str(tmp_path), files, SourceGraph(), {})
    names = {e.name for e in model.entities}
    assert "User" in names
    user = next(e for e in model.entities if e.name == "User")
    assert {c.name for c in user.columns} >= {"id", "email"}
    assert user.source_kind == "django_migration"


def test_sql_alter_table_add_column(tmp_path):
    (tmp_path / "schema.sql").write_text(
        "CREATE TABLE users (id int);\n"
        "ALTER TABLE users ADD COLUMN email varchar(255);\n",
        encoding="utf-8")
    files = FileInventory(str(tmp_path)).scan()
    model = DataAnalyzer().analyze(str(tmp_path), files, SourceGraph(), {})
    users = next(e for e in model.entities if e.name == "users")
    assert any(c.name == "email" for c in users.columns)
