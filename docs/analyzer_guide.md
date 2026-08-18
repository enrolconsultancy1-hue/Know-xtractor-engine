# Analyzer Guide

Analyzers are modular, independently testable units selected dynamically from
repository contents via a registry. There is no central switch statement: the
pipeline asks the registry which analyzers apply.

## Anatomy of an analyzer

Every analyzer subclasses `app.analyzers.base.BaseAnalyzer`:

```python
class MyAnalyzer(BaseAnalyzer):
    name = "my_language"                      # registry key

    def applicable(self, files: list[FileEntry]) -> bool:
        return any(f.language == "my_language" for f in files)

    def analyze(self, root, files, graph, ctx):
        # 1. read files (respect size/binary flags)
        # 2. parse structure into SourceModule / Symbol / Import
        # 3. mutate `graph` and/or return a domain result
        return graph
```

## The source graph

`app/analyzers/source_graph.py` defines the shared intermediate index:

- `FileEntry` — one discovered file (path, category, language, size, binary).
- `SourceModule` — imports, symbols, calls, errors for one file.
- `Symbol` — name, kind (class/function/method/model/route/component), decorators,
  bases, calls, params, returns.
- `SourceGraph` — the aggregate with reverse-dependency helpers.

Analyzers populate this graph; extractors (`app/extractors/`) turn it into
domain objects (`Component`, `Workflow`, …).

## Adding a language analyzer

1. Create `app/analyzers/mylang.py` with a `BaseAnalyzer` subclass.
2. Add a language mapping entry in `inventory.py` (`_EXT_TO_LANG`) so files are
   classified with the right language.
3. Register it in `app/services/pipeline.py` (`_register_default_analyzers`).
4. Add `app/domain` models if the language needs new entity kinds (rare).
5. Add a test fixture and a `tests/test_mylang.py`.

## Deterministic vs. AI

The rule is: **use deterministic static analysis wherever possible**. AI is
reserved for semantic interpretation and reasoning. The `app/ai/` package
provides a pluggable `AIProvider` abstraction (`openai`, `anthropic`, `gemini`,
or `none`). Set `KNOX_AI_PROVIDER` to enable one.

## Built-in analyzers

| Analyzer | Scope |
|----------|-------|
| `languages` | languages, frameworks, databases, infra |
| `dependencies` | requirements.txt, package.json, go.mod, pyproject, Cargo |
| `python` | AST: classes, functions, imports, models, routes |
| `javascript` | JS/TS: imports, exports, functions, components, hooks |
| `generic` | Go, Rust, Java, C#, PHP, Ruby, Kotlin, Dart (heuristic) |
| `api` | HTTP endpoints (FastAPI, Flask, Express) |
| `data` | SQLAlchemy / Django / Pydantic models + SQL |
| `config` | env/YAML/JSON/TOML/INI/Dockerfile (secrets redacted) |
| `tests` | test functions, assertions, fixtures/mocks |
| `docs` | headings, tech claims, doc↔source discrepancies |
