"""Data model discovery: SQLAlchemy / Django / Pydantic models and SQL files."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from app.analyzers.base import BaseAnalyzer
from app.analyzers.source_graph import FileEntry, SourceGraph
from app.domain.common import Confidence, Evidence
from app.domain.data_model import DataColumn, DataEntity, DataModel, DataRelationship

_SQLALCHEMY_TYPES = {
    "Integer": "integer", "String": "string", "Text": "text", "Boolean": "boolean",
    "Float": "float", "DateTime": "datetime", "Date": "date", "JSON": "json",
    "ForeignKey": "foreign_key", "Numeric": "numeric", "UUID": "uuid",
    "Enum": "enum", "LargeBinary": "binary",
}

# Alembic / Django migration declarations.
_ALEMBIC_CREATE_TABLE = re.compile(r"op\.create_table\(\s*['\"]([\w]+)['\"]", re.I)
_ALEMBIC_COLUMN = re.compile(r"sa\.Column\(\s*['\"]([\w]+)['\"]\s*,\s*sa\.([A-Za-z]+)", re.I)
_ALEMBIC_ADD_COLUMN = re.compile(
    r"op\.add_column\(\s*['\"]([\w]+)['\"]\s*,\s*sa\.Column\(\s*['\"]([\w]+)['\"]\s*,\s*sa\.([A-Za-z]+)", re.I
)
_DJANGO_CREATE_MODEL = re.compile(r"migrations\.CreateModel\(\s*name\s*=\s*['\"]([\w]+)['\"]", re.I)
_DJANGO_FIELD = re.compile(r"\(\s*['\"]([\w]+)['\"]\s*,\s*models\.([A-Za-z]+)", re.I)
_DJANGO_ADD_FIELD = re.compile(
    r"migrations\.AddField\(\s*model_name\s*=\s*['\"]([\w]+)['\"]\s*,\s*name\s*=\s*['\"]([\w]+)['\"]\s*,\s*field\s*=\s*models\.([A-Za-z]+)", re.I
)
_ALTER_ADD_COLUMN = re.compile(
    r"ALTER\s+TABLE\s+(?:IF\s+EXISTS\s+)?[\"']?([\w.]+)[\"']?\s+ADD(?:\s+COLUMN)?\s+[\"']?(\w+)[\"']?\s+([A-Za-z0-9_()]+)", re.I
)


class DataAnalyzer(BaseAnalyzer):
    name = "data"

    def applicable(self, files: list[FileEntry]) -> bool:
        return any(f.language in ("python", "sql") for f in files)

    def analyze(self, root: str, files: list[FileEntry], graph: SourceGraph, ctx: dict) -> DataModel:
        model = DataModel()
        root_path = Path(root)
        for f in files:
            if f.is_binary:
                continue
            if f.language == "python":
                self._python_entities(root_path / f.path, f.path, model)
                self._python_migrations(root_path / f.path, f.path, model)
            elif f.language == "sql":
                self._sql_entities(root_path / f.path, f.path, model)
        # Infer relationships from foreign keys.
        for ent in model.entities:
            for col in ent.columns:
                if col.foreign_key:
                    target = col.name.removesuffix("_id").capitalize()
                    if any(e.name.lower() == target.lower() for e in model.entities):
                        model.relationships.append(DataRelationship(
                            source=ent.name, target=target, via=col.name,
                        ))
        return model

    def _python_entities(self, path: Path, rel: str, model: DataModel) -> None:
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return
        try:
            tree = ast.parse(source, filename=rel)
        except SyntaxError:
            return
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            bases = [self._name(b) for b in node.bases]
            is_django = any("Model" in b for b in bases) and "models" in " ".join(bases)
            is_sqlalchemy = any(b == "Base" or "declarative" in b for b in bases) or any(
                isinstance(n, ast.Assign) and
                any(isinstance(t, ast.Name) and t.id == "__tablename__" for t in n.targets)
                for n in node.body
            )
            is_pydantic = any(b == "BaseModel" for b in bases)

            if not (is_sqlalchemy or is_django or is_pydantic):
                continue

            source_kind = "sqlalchemy" if is_sqlalchemy else ("django" if is_django else "pydantic")
            columns: list[DataColumn] = []
            for item in node.body:
                if isinstance(item, ast.Assign) and item.targets:
                    tgt = self._name(item.targets[0])
                    if not tgt:
                        continue
                    if isinstance(item.targets[0], ast.Name) and item.targets[0].id == "__tablename__":
                        continue
                    col = self._column_from_assignment(item, source_kind)
                    if col:
                        columns.append(col)
                elif isinstance(item, ast.AnnAssign) and item.target:
                    name = self._name(item.target)
                    typ = self._name(item.annotation)
                    columns.append(DataColumn(name=name, type=typ or "unknown", nullable=True))

            if columns:
                model.entities.append(DataEntity(
                    name=node.name, kind="model", columns=columns,
                    source_file=rel, source_kind=source_kind,
                    confidence=Confidence(score=0.85, rationale=f"{source_kind} model detected"),
                    evidence=[Evidence(file=rel, symbol=node.name, reason=f"{source_kind} model class")],
                ))

    def _column_from_assignment(self, node: ast.Assign, source_kind: str) -> DataColumn | None:
        if not isinstance(node.value, ast.Call):
            return None
        target_name = self._name(node.targets[0])
        if not target_name:
            return None
        func = self._name(node.value.func)
        col = DataColumn(name=target_name)
        col.default = None
        if source_kind == "sqlalchemy" and "Column" in func:
            # First positional arg is the type.
            if node.value.args:
                typ = self._name(node.value.args[0])
                col.type = _SQLALCHEMY_TYPES.get(typ.split(".")[-1], typ.split(".")[-1].lower())
            for kw in node.value.keywords:
                if kw.arg == "primary_key" and isinstance(kw.value, ast.Constant) and kw.value.value:
                    col.primary_key = True
                    col.nullable = False
                if kw.arg == "nullable" and isinstance(kw.value, ast.Constant) and kw.value.value is False:
                    col.nullable = False
                if kw.arg == "default":
                    col.default = self._name(kw.value)
            if "ForeignKey" in func or any("ForeignKey" in self._name(a) for a in node.value.args):
                col.foreign_key = True
            return col
        if source_kind == "django" and "Field" in func:
            typ = func.split(".")[-1].replace("Field", "").lower()
            col.type = typ or "unknown"
            return col
        return None

    def _sql_entities(self, path: Path, rel: str, model: DataModel) -> None:
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return
        # CREATE TABLE statements.
        for m in re.finditer(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"']?([\w.]+)[\"']?\s*\(([\s\S]*?)\);", source, re.I):
            table = m.group(1).split(".")[-1]
            body = m.group(2)
            columns: list[DataColumn] = []
            for line in body.split(","):
                line = line.strip()
                cm = re.match(r"[\"']?(\w+)[\"']?\s+([A-Za-z0-9_()]+)", line)
                if cm:
                    name, typ = cm.group(1), cm.group(2)
                    columns.append(DataColumn(
                        name=name, type=typ.lower(),
                        primary_key="PRIMARY KEY" in line.upper(),
                        foreign_key="REFERENCES" in line.upper(),
                    ))
            if columns:
                model.entities.append(DataEntity(
                    name=table, kind="table", columns=columns, source_file=rel,
                    source_kind="sql", confidence=Confidence(score=0.9, rationale="CREATE TABLE"),
                    evidence=[Evidence(file=rel, reason="CREATE TABLE statement")],
                ))
            model.engines.append("sql")

        # ALTER TABLE ... ADD COLUMN statements (columns added by migrations).
        for m in _ALTER_ADD_COLUMN.finditer(source):
            self._add_column(
                model, m.group(1).split(".")[-1],
                DataColumn(name=m.group(2), type=m.group(3).lower()),
                rel, "sql",
            )

    def _python_migrations(self, path: Path, rel: str, model: DataModel) -> None:
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return
        if not source:
            return
        if "op.create_table" in source or "op.add_column" in source:
            self._alembic(source, rel, model)
        if "migrations.CreateModel" in source or "migrations.AddField" in source:
            self._django(source, rel, model)

    def _alembic(self, source: str, rel: str, model: DataModel) -> None:
        creates = list(_ALEMBIC_CREATE_TABLE.finditer(source))
        columns = list(_ALEMBIC_COLUMN.finditer(source))
        add_columns = list(_ALEMBIC_ADD_COLUMN.finditer(source))
        add_spans = [(m.start(), m.end()) for m in add_columns]
        for i, cm in enumerate(creates):
            table = cm.group(1)
            end = creates[i + 1].start() if i + 1 < len(creates) else len(source)
            cols = [
                DataColumn(name=c.group(1), type=c.group(2).lower())
                for c in columns
                if cm.end() <= c.start() < end and not any(s <= c.start() < e for s, e in add_spans)
            ]
            self._add_entity(model, table, cols, rel, "alembic")
        for m in add_columns:
            self._add_column(model, m.group(1), DataColumn(name=m.group(2), type=m.group(3).lower()), rel, "alembic")

    def _django(self, source: str, rel: str, model: DataModel) -> None:
        creates = list(_DJANGO_CREATE_MODEL.finditer(source))
        fields = list(_DJANGO_FIELD.finditer(source))
        for i, cm in enumerate(creates):
            name = cm.group(1)
            end = creates[i + 1].start() if i + 1 < len(creates) else len(source)
            cols = [
                DataColumn(name=fm.group(1), type=fm.group(2).replace("Field", "").lower())
                for fm in fields
                if cm.end() <= fm.start() < end
            ]
            self._add_entity(model, name, cols, rel, "django_migration")
        for m in _DJANGO_ADD_FIELD.finditer(source):
            self._add_column(
                model, m.group(1),
                DataColumn(name=m.group(2), type=m.group(3).replace("Field", "").lower()),
                rel, "django_migration",
            )

    def _add_entity(self, model: DataModel, name: str, columns: list[DataColumn], rel: str, source_kind: str) -> None:
        existing = next((e for e in model.entities if e.name.lower() == name.lower()), None)
        if existing is None:
            model.entities.append(DataEntity(
                name=name, kind="table", columns=columns, source_file=rel, source_kind=source_kind,
                confidence=Confidence(score=0.8, rationale=f"{source_kind} schema declaration"),
                evidence=[Evidence(file=rel, reason=f"{source_kind} schema declaration")],
            ))
        else:
            for col in columns:
                if not any(c.name == col.name for c in existing.columns):
                    existing.columns.append(col)

    def _add_column(self, model: DataModel, table: str, column: DataColumn, rel: str, source_kind: str) -> None:
        self._add_entity(model, table, [column], rel, source_kind)

    @staticmethod
    def _name(node: ast.expr | None) -> str:
        if node is None:
            return ""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            base = DataAnalyzer._name(node.value)
            return f"{base}.{node.attr}" if base else node.attr
        if isinstance(node, ast.Subscript):
            return DataAnalyzer._name(node.value)
        if isinstance(node, ast.Call):
            return DataAnalyzer._name(node.func)
        if isinstance(node, ast.Constant):
            return str(node.value)
        return ""
