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
pip install -r requirements-dev.txt   # runtime + test/lint/coverage tools
```

`requirements.txt` holds runtime-only dependencies (used by the Docker image);
`requirements-dev.txt` adds pytest, ruff, mypy, and coverage on top of it.

## Database setup

The schema is owned by Alembic. Before the first run (and after pulling new
migrations), apply migrations:

```bash
cd backend
python -m alembic upgrade head
```

> **Recovering a database created by older KNOX builds:** those builds
> auto-created tables with `create_all` (no Alembic stamp). If `alembic upgrade
> head` fails with `table projects already exists`, reset the dev DB and migrate
> fresh:
>
> ```powershell
> # stop any running uvicorn first, then from backend/:
> Remove-Item data\knox.db
> python -m alembic upgrade head
> ```
>
> Production databases (PostgreSQL) never hit this path because they are
> created empty and migrated with Alembic.

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
python -m ruff check .      # lint
python -m mypy app          # type check
python -m pytest -q         # tests
```

Pytest uses an isolated temp dir under `backend/.pytest-tmp` (gitignored) so it
does not depend on the OS temp folder. API tests create a throwaway SQLite DB and
override the session dependency, so they never touch `data/knox.db`.

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
- **Run a migration:** `cd backend; python -m alembic upgrade head` (new ones via
  `python -m alembic revision --autogenerate -m "..."`).
- **Analyze a remote repo (no UI):** `cd backend; python analyze_remote.py <url> [branch]`.

## Limitations (documented, not hidden)

- JS/TS/TSX/Vue/Svelte are parsed with tree-sitter (see
  `app/analyzers/treesitter.py`); other non-Python languages fall back to
  heuristic (regex) analysis.
- The analysis runner uses an in-process FIFO queue with a worker pool
  (`app/services/queue.py`); a production deployment can swap in Celery/RQ
  (`app/services/runner.py` is the only transport-specific module).
- PDF export is a simple text renderer (fpdf2); Markdown/JSON are the primary formats.
- Database schema is managed exclusively with Alembic (`migrations/`); the app
  no longer calls `create_all` at startup. `app.db.session.init_db()` remains
  only as a legacy dev helper.
