# Development Guide

## Prerequisites

- Python 3.11+ (tested on 3.13)
- Node 18+ and npm (for the frontend)
- Git

## Backend setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows  (source .venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
```

## Running

```bash
# Backend (API + OpenAPI docs at /docs)
uvicorn app.main:app --reload --port 8000

# Frontend dev server (proxies /api → :8000)
cd ../frontend
npm install
npm run dev
```

## Configuration

All settings are read from environment variables (prefix `KNOX_`) or a `.env`
file. See `backend/app/core/config.py` for the full list. Key ones:

| Variable | Default | Purpose |
|----------|---------|---------|
| `KNOX_DATABASE_URL` | `sqlite:///./data/knox.db` | SQLAlchemy URL |
| `KNOX_WORKSPACE_DIR` | `analysis_workspace` | where repos are cloned |
| `KNOX_PACKAGES_DIR` | `knowledge_packages` | where packages are stored |
| `KNOX_MAX_FILE_SIZE_BYTES` | `2097152` | per-file size limit |
| `KNOX_ALLOW_NETWORK_CLONE` | `true` | allow remote clones |
| `KNOX_AI_PROVIDER` | `none` | `none`/`openai`/`anthropic`/`gemini` |

## Quality tooling

```bash
cd backend
ruff check .          # lint
mypy app              # type check
pytest                # tests
```

The frontend uses TypeScript (strict), and Vite for bundling.

## Testing

Tests build small fixture repositories programmatically (see
`backend/tests/conftest.py`), so no network is required. Coverage targets the
major subsystems: inventory, language detection, Python AST, dependencies,
API/data/workflow extraction, sprint clustering, knowledge assembly, security,
and API endpoints.

## Common tasks

- **Analyze a repo end-to-end (no UI):** use the API calls in `API.md`.
- **Add a language analyzer:** see `ANALYZER_GUIDE.md`.
- **Enable AI reasoning:** set `KNOX_AI_PROVIDER` + the matching API key env var.
- **Reset data:** delete `data/`, `analysis_workspace/`, `knowledge_packages/`.

## Limitations (documented, not hidden)

- JS/TS and other non-Python languages use heuristic (regex) analysis; deep AST
  adapters (e.g. tree-sitter) are the intended extension point.
- The analysis runner uses in-process threads; a production deployment should
  swap in Celery/RQ (`app/services/runner.py` is the only transport-specific module).
- PDF export is a simple text renderer (fpdf2); Markdown/JSON are the primary formats.
- Database migrations use `create_all`; add Alembic for real schema evolution.
