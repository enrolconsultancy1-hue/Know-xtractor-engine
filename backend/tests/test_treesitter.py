"""Tests for the tree-sitter JS/TS analyzer."""

import pytest

from app.analyzers.inventory import FileInventory
from app.analyzers.source_graph import SourceGraph
from app.analyzers.treesitter import _TREE_SITTER_AVAILABLE, TreeSitterJsAnalyzer

JS_SAMPLE = """
import React, { useState, useEffect } from 'react';
import express from 'express';
import { getUsers } from './services/userService';

const app = express();

export function formatName(name) {
  return name.trim();
}

export default class UserStore {
  constructor() { this.users = []; }
  addUser(u) { this.users.push(u); }
}

function App() {
  const [count, setCount] = useState(0);
  useEffect(() => { getUsers(); }, []);
  return <div>{count}</div>;
}

const Sidebar = () => <nav />;

app.get('/users', (req, res) => res.json([]));
router.post('/users', createUser);

// @app.get("/fake")  <- must NOT be parsed as a route (comment)
"""


@pytest.mark.skipif(not _TREE_SITTER_AVAILABLE, reason="tree-sitter not installed")
def test_extracts_imports_exports_functions_classes(tmp_path):
    (tmp_path / "sample.js").write_text(JS_SAMPLE, encoding="utf-8")
    files = FileInventory(str(tmp_path)).scan()
    graph = SourceGraph()
    TreeSitterJsAnalyzer().analyze(str(tmp_path), files, graph, {})
    module = graph.modules["sample.js"]

    imports = {i.module for i in module.imports}
    assert "react" in imports
    assert "express" in imports
    assert "./services/userService" in imports

    symbols = {s.name for s in module.symbols}
    assert "formatName" in symbols
    assert "UserStore" in symbols
    # React components detected via uppercase function/class.
    assert "App" in symbols
    assert "Sidebar" in symbols

    calls = module.calls
    assert "useState" in calls
    assert "useEffect" in calls


@pytest.mark.skipif(not _TREE_SITTER_AVAILABLE, reason="tree-sitter not installed")
def test_extracts_routes_and_ignores_comments(tmp_path):
    (tmp_path / "app.js").write_text(JS_SAMPLE, encoding="utf-8")
    files = FileInventory(str(tmp_path)).scan()
    graph = SourceGraph()
    TreeSitterJsAnalyzer().analyze(str(tmp_path), files, graph, {})
    module = graph.modules["app.js"]
    route_calls = [c for c in module.calls if c.startswith(("get", "post", "put", "delete", "use"))]
    assert "get /users" in route_calls
    assert "post /users" in route_calls
    # The commented-out route must NOT appear.
    assert not any("/fake" in c for c in route_calls)


def test_applicable_returns_false_without_js(tmp_path):
    (tmp_path / "x.py").write_text("x = 1", encoding="utf-8")
    files = FileInventory(str(tmp_path)).scan()
    assert TreeSitterJsAnalyzer().applicable(files) is False
