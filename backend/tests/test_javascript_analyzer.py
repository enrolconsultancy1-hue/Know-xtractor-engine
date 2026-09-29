"""Tests for JavaScript/TypeScript heuristic analyzer."""

from __future__ import annotations

from pathlib import Path

from app.analyzers.javascript import JavaScriptAnalyzer
from app.analyzers.source_graph import FileEntry, SourceGraph, SymbolKind


def test_javascript_analyzer_applicable():
    analyzer = JavaScriptAnalyzer()
    assert analyzer.applicable([FileEntry(path="src/index.ts", language="typescript", size=100)])
    assert analyzer.applicable([FileEntry(path="src/App.vue", language="vue", size=100)])
    assert analyzer.applicable([FileEntry(path="src/Component.svelte", language="svelte", size=100)])
    assert not analyzer.applicable([FileEntry(path="main.py", language="python", size=100)])


def test_javascript_analyzer_parses_symbols(tmp_path: Path):
    js_content = """
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { User, Role } from './types';

export class UserService extends BaseService {
    getUser() {}
}

export function fetchUserProfile(userId) {
    return axios.get(`/users/${userId}`);
}

export const helperArrow = (x) => {
    return x * 2;
};

export const UserProfileCard = ({ user }) => {
    const auth = useAuth();
    useEffect(() => {
        // do something
    }, []);
    return <div>User Card</div>;
};

function SettingsPanel() {
    const theme = useTheme();
    return <div>Settings</div>;
}
"""
    file_path = tmp_path / "App.tsx"
    file_path.write_text(js_content, encoding="utf-8")

    files = [
        FileEntry(path="App.tsx", language="typescript", size=len(js_content)),
        FileEntry(path="image.png", language="binary", size=50, is_binary=True),
        FileEntry(path="other.py", language="python", size=50),
    ]

    analyzer = JavaScriptAnalyzer()
    graph = SourceGraph()
    analyzer.analyze(str(tmp_path), files, graph, ctx={})

    assert len(graph.modules) == 1
    mod = graph.modules["App.tsx"]
    assert mod.path == "App.tsx"
    assert mod.language == "javascript"

    # Verify imports
    import_modules = {imp.module for imp in mod.imports}
    assert "react" in import_modules
    assert "axios" in import_modules
    assert "./types" in import_modules

    # Verify symbols
    classes = [s for s in mod.symbols if s.kind == SymbolKind.CLASS]
    assert len(classes) == 1
    assert classes[0].name == "UserService"
    assert classes[0].bases == ["BaseService"]

    funcs = [s for s in mod.symbols if s.kind == SymbolKind.FUNCTION]
    func_names = {f.name for f in funcs}
    assert "fetchUserProfile" in func_names
    assert "helperArrow" in func_names

    # React components
    components = [s for s in mod.symbols if s.kind == SymbolKind.COMPONENT]
    comp_names = {c.name for c in components}
    assert "UserProfileCard" in comp_names
    assert "SettingsPanel" in comp_names

    # Hooks called
    assert "useAuth" in mod.calls
    assert "useTheme" in mod.calls


def test_javascript_analyzer_handles_read_error(tmp_path: Path):
    analyzer = JavaScriptAnalyzer()
    graph = SourceGraph()
    files = [FileEntry(path="missing.js", language="javascript", size=10)]
    analyzer.analyze(str(tmp_path), files, graph, ctx={})

    assert len(graph.modules) == 1
    assert len(graph.modules["missing.js"].errors) > 0

