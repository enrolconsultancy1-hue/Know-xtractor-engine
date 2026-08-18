"""Tests for the Go/Rust/Java/C#/Ruby/PHP tree-sitter analyzers."""

from app.analyzers.inventory import FileInventory
from app.analyzers.source_graph import SourceGraph, SymbolKind
from app.analyzers.treesitter_general import TreeSitterGeneralAnalyzer

ANALYZER = TreeSitterGeneralAnalyzer()


def _parse(tmp_path, filename: str, content: str):
    (tmp_path / filename).write_text(content, encoding="utf-8")
    files = FileInventory(str(tmp_path)).scan()
    graph = ANALYZER.analyze(str(tmp_path), files, SourceGraph(), {})
    return graph.modules.get(filename)


def _names(mod, kind):
    return {s.name for s in mod.symbols if s.kind == kind}


def test_go_symbols_imports_calls(tmp_path):
    mod = _parse(tmp_path, "main.go", (
        'package main\nimport "fmt"\n'
        'func save(x int) { db.Query("x"); fmt.Println("y") }\n'
        'type User struct { Name string }\n'
    ))
    assert "save" in _names(mod, SymbolKind.FUNCTION)
    assert "User" in _names(mod, SymbolKind.CLASS)
    assert "fmt" in {i.module for i in mod.imports}
    assert "db.Query" in mod.calls


def test_rust_symbols_imports_calls(tmp_path):
    mod = _parse(tmp_path, "main.rs", (
        'use std::collections::HashMap;\n'
        'fn save() { get(1); self.x(); }\n'
        'struct User { name: String }\n'
    ))
    assert "save" in _names(mod, SymbolKind.FUNCTION)
    assert "User" in _names(mod, SymbolKind.CLASS)
    assert "std::collections::HashMap" in {i.module for i in mod.imports}
    assert "self.x" in mod.calls


def test_java_method_and_calls(tmp_path):
    mod = _parse(tmp_path, "User.java", (
        'import java.util.List;\n'
        'class User { void save() { session.save(this); } }\n'
    ))
    assert "User" in _names(mod, SymbolKind.CLASS)
    assert "save" in _names(mod, SymbolKind.FUNCTION)
    assert "java.util.List" in {i.module for i in mod.imports}
    assert "session.save" in mod.calls


def test_csharp_method_and_calls(tmp_path):
    mod = _parse(tmp_path, "User.cs", (
        'using System;\n'
        'class User { void Save() { client.GetAsync(); } }\n'
    ))
    assert "User" in _names(mod, SymbolKind.CLASS)
    assert "Save" in _names(mod, SymbolKind.FUNCTION)
    assert "System" in {i.module for i in mod.imports}
    assert "client.GetAsync" in mod.calls


def test_ruby_require_method_and_calls(tmp_path):
    mod = _parse(tmp_path, "user.rb", (
        'require "json"\n'
        'class User\n  def save\n    user.save\n  end\nend\n'
    ))
    assert "User" in _names(mod, SymbolKind.CLASS)
    assert "save" in _names(mod, SymbolKind.FUNCTION)
    assert "json" in {i.module for i in mod.imports}
    assert "user.save" in mod.calls


def test_php_namespace_method_and_calls(tmp_path):
    mod = _parse(tmp_path, "User.php", (
        '<?php\nuse Foo\\Bar;\n'
        'class User { function save() { $db->query("x"); } }\n'
    ))
    assert "User" in _names(mod, SymbolKind.CLASS)
    assert "save" in _names(mod, SymbolKind.FUNCTION)
    assert "Foo\\Bar" in {i.module for i in mod.imports}
    assert "$db.query" in mod.calls


def test_analyzer_handles_multiple_languages(tmp_path):
    (tmp_path / "a.go").write_text('package main\nfunc f() { db.Query("x") }\n', encoding="utf-8")
    (tmp_path / "b.rs").write_text('fn g() { redis.get() }\n', encoding="utf-8")
    (tmp_path / "c.py").write_text("def h(): return 1\n", encoding="utf-8")
    files = FileInventory(str(tmp_path)).scan()
    graph = ANALYZER.analyze(str(tmp_path), files, SourceGraph(), {})
    assert "a.go" in graph.modules
    assert "b.rs" in graph.modules
    # Python is not this analyzer's responsibility.
    assert "c.py" not in graph.modules


def test_applicable_only_for_supported_languages(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    files = FileInventory(str(tmp_path)).scan()
    assert ANALYZER.applicable(files) is False


def test_go_gin_pipeline_produces_workflow_with_persistence(tmp_path):
    from app.services.pipeline import AnalysisPipeline, PipelineContext

    (tmp_path / "main.go").write_text(
        'package main\n'
        'import "github.com/gin-gonic/gin"\n'
        'func main() {\n'
        '    r := gin.Default()\n'
        '    r.GET("/users", listUsers)\n'
        '    r.Run()\n'
        '}\n'
        'func listUsers(c *gin.Context) {\n'
        '    rows := db.Query("SELECT * FROM users")\n'
        '    c.JSON(200, rows)\n'
        '}\n',
        encoding="utf-8")
    (tmp_path / "go.mod").write_text("module example\n\ngo 1.21\n", encoding="utf-8")

    ctx = PipelineContext(repository="gin", repo_path=str(tmp_path))
    pkg = AnalysisPipeline().run(ctx)
    wf = next((w for w in pkg.workflows if "users" in w.name), None)
    assert wf is not None
    assert any("db.Query" in s.name for s in wf.steps)
