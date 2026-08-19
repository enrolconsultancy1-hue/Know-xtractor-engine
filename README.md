# KNOX — Knowledge eXtraction & Architectural Reconstruction Engine

KNOX transforms an open-source GitHub repository into a **structured, implementation-ready architectural knowledge package**. It does *not* summarize the repo, and it does *not* copy the source code. It extracts **understanding**: concepts, architecture, relationships, workflows, data models, APIs, decisions, constraints, and evolution — each backed by evidence and classified as **fact / inference / hypothesis**.

```
Repository → Pure Knowledge → Architecture → Custom Architecture → Implementation-Ready Prompt
```

## What KNOX does

1. **Acquires** a repository safely (isolated, read-only workspace; no code execution).
2. **Inventories** files with `.gitignore` support, binary/generated detection, and size limits.
3. **Detects** the technology stack (languages, frameworks, databases, infrastructure).
4. **Parses** source structurally (Python via AST; JS/TS and 8 more languages via adapters).
5. **Discovers** components, dependencies, APIs, data models, and workflows.
6. **Analyzes** configuration (secrets redacted), tests (as behavioral evidence), and docs.
7. **Reads git history** and clusters commits into **architectural sprints**.
8. **Builds a queryable knowledge graph** with evidence and confidence.
9. **Reconstructs** a technology-neutral architecture, then binds it to concrete tech.
10. **Lets you customize** the tech stack and **generates a single implementation prompt**.

## Repository layout

```
knox/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI routers
│   │   ├── core/           # config, logging, security
│   │   ├── domain/         # Pydantic knowledge model (the "pure knowledge" schema)
│   │   ├── db/             # SQLAlchemy models + session
│   │   ├── analyzers/      # plugin registry + per-language/domain analyzers
│   │   ├── extractors/     # component & workflow discovery
│   │   ├── knowledge/      # knowledge graph builder
│   │   ├── architecture/   # discovery, reconstruction, customization
│   │   ├── git/            # history + sprint clustering
│   │   ├── ai/             # optional AI provider abstraction
│   │   ├── services/       # acquisition, pipeline, knowledge assembly, export, runner
│   │   └── main.py         # FastAPI app
│   ├── tests/              # pytest suite + fixture repos
│   ├── requirements.txt
│   └── pyproject.toml      # ruff / mypy / pytest config
├── frontend/               # React + TypeScript + Vite
├── analysis_workspace/     # cloned repos (gitignored)
├── knowledge_packages/     # persisted JSON packages (gitignored)
├── exports/                # markdown/json/yaml/pdf exports (gitignored)
├── data/                   # SQLite database (gitignored)
└── docs/                   # ARCHITECTURE.md, API.md, ...
```

## Quick start

### Backend

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000/docs for the interactive API.

### Frontend

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173 (proxies /api to :8000)
```

### Analyze a repository

Either use the UI (**New Analysis** → paste URL → Analyze), or the API:

```bash
curl -X POST http://localhost:8000/api/projects \
  -H "Content-Type: application/json" \
  -d '{"repository_url": "https://github.com/fastapi/fastapi.git"}'

curl -X POST http://localhost:8000/api/projects/1/analyze \
  -H "Content-Type: application/json" -d '{"branch": "master"}'
```

Then poll `GET /api/analysis/{id}` until `status == "done"`, and read
`GET /api/projects/1/knowledge`.

### Run tests

```bash
cd backend
pytest
```

## Core principles

- **Source ≠ knowledge.** The final package contains understanding + evidence references, never a copy of the source.
- **FACT / INFERENCE / HYPOTHESIS.** Every statement is classified, and knowledge without evidence gets lower confidence.
- **Deterministic first, AI second.** Static analysis (AST, manifests, git) is the default; AI is an optional pluggable layer.
- **Untrusted input.** Repositories are never executed; secrets are never persisted; paths are guarded.

## Documentation

- [QUICKSTART.md](docs/QUICKSTART.md) — clone → install → analyze a real repo → build prompt (Windows)
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — system design and pipeline
- [DEVELOPMENT.md](docs/DEVELOPMENT.md) — setup, tooling, contribution
- [API.md](docs/API.md) — REST API reference
- [KNOWLEDGE_MODEL.md](docs/KNOWLEDGE_MODEL.md) — the canonical schema
- [ANALYZER_GUIDE.md](docs/ANALYZER_GUIDE.md) — adding new language analyzers
- [SECURITY.md](docs/SECURITY.md) — threat model and controls
