# KNOX Architecture

## System overview

KNOX is a clean, modular monolith: a FastAPI backend that runs a multi-stage
**analysis pipeline**, and a React/TypeScript frontend that visualizes the
resulting **knowledge package**.

```
                        ┌──────────────────────────────┐
                        │        React frontend        │
                        └──────────────┬───────────────┘
                                       │ HTTP / SSE
                        ┌──────────────▼───────────────┐
                        │        FastAPI (api/)        │
                        │  projects · analysis ·       │
                        │  knowledge · architecture    │
                        └──────────────┬───────────────┘
                                       │
                        ┌──────────────▼───────────────┐
                        │   services/pipeline.py       │
                        │   orchestrates stages        │
                        └──────────────┬───────────────┘
        ┌───────────────────┬──────────┼──────────┬───────────────────┐
        ▼                   ▼          ▼          ▼                   ▼
   analyzers/         extractors/   knowledge/  architecture/       git/
   (inventory,        (components,  (graph)    (discovery,          (history,
    languages,         workflows)              reconstruction,       sprints)
    AST, api, data,                            customization)
    config, tests, docs)
                        └──────────────┬───────────────┘
                                       ▼
                        ┌──────────────────────────────┐
                        │   services/knowledge_extractor│
                        │   → KnowledgePackage (domain/)│
                        └──────────────────────────────┘
```

## Pipeline stages

1. `repository_acquisition` — clone into an isolated workspace.
2. `file_inventory` — scan, filter, classify, cap sizes/counts.
3. `language_detection` — languages, frameworks, databases, infra.
4. `static_analysis` — AST/structural parsing via the analyzer registry.
5. `dependency_analysis` — manifests (requirements.txt, package.json, …).
6. `api_discovery` / `data_model` / `config` / `tests` / `docs`.
7. `workflow_extraction` — flows from entry points and routes.
8. `architecture_discovery` — evidence-weighted pattern scoring.
9. `git_analysis` — commit history + sprint clustering.
10. `knowledge_synthesis` — assemble the `KnowledgePackage`.
11. `architecture_reconstruction` — technology-neutral design + binding.

## Four layers of representation

KNOX strictly separates:

| Layer | Meaning | Where |
|-------|---------|-------|
| **Source implementation** | actual code, transient | `analysis_workspace/` (never persisted) |
| **Extracted knowledge** | understanding + evidence refs | `domain/` → `KnowledgePackage` |
| **Architectural design** | technology-neutral design | `domain/architecture.py` `ReconstructedArchitecture` |
| **Implementation specification** | instructions for another agent | `domain/implementation.py` `ImplementationSpec` |

## Analyzer plugin system

`app/analyzers/base.py` defines `BaseAnalyzer` (`applicable()` + `analyze()`).
`app/analyzers/registry.py` holds an `AnalyzerRegistry` that selects analyzers
per repository. Adding a language = adding one module and registering it.

## Knowledge model

All domain objects are Pydantic models in `app/domain/` — strongly typed,
serializable to JSON (canonical), YAML, Markdown, and PDF. Evidence and
confidence are first-class on every extracted object.

## Data storage

- **SQLite** (via SQLAlchemy) stores `projects` and `analysis_runs` (status,
  progress, summary, errors/warnings).
- **Knowledge packages** are stored as JSON files under `knowledge_packages/`
  so they are portable and diff-able; the DB keeps only lightweight metadata.
