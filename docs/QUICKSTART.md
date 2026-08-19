# KNOX Quickstart (Windows terminal)

End-to-end from a fresh clone to a customized, implementation-ready rebuild
prompt for a real open-source repository. All commands are Windows
PowerShell; they work in CMD/`cmd` with minor quoting differences.

## 0. Prerequisites

- [Git for Windows](https://git-scm.com/downloads)
- Python 3.11-3.14 (KNOX is verified on 3.13 and 3.14; wheels included)
- Node.js 20+ — **only needed if you want the React frontend UI**. The CLI
  and API flows below run with Python alone.

Check:

```powershell
git --version
python --version
```

## 1. Clone & install

```powershell
cd C:\Users\HP\Projects
git clone https://github.com/enrolconsultancy1-hue/Know-xtractor-engine.git knox
cd knox\backend

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Configuration + database schema
Copy-Item .env.example .env
alembic upgrade head

# Sanity check: full test suite
python -m pytest -q
```

Expected: `119 passed, 2 skipped` (the 2 skips are Redis/RQ integration tests
that only run when Redis is present).

## 2. Boot the API

```powershell
uvicorn app.main:app --reload --port 8000
```

Interactive API docs (Swagger): http://localhost:8000/docs

Health checks (separate terminal):

```powershell
Invoke-RestMethod http://localhost:8000/healthz
Invoke-RestMethod http://localhost:8000/readyz
```

## 3. Fastest real-project test (one CLI command, no UI)

```powershell
python analyze_remote.py https://github.com/pallets/flask.git main
```

This clones the repo into the isolated workspace, runs the full 12-stage
pipeline, prints architecture + facts + component/workflow/API counts, and
saves artifacts to `backend\exports\demo_remote\`:

| Artifact | Contents |
|---|---|
| `flask_knowledge_package.json` | The structured knowledge package |
| `flask_implementation_prompt.md` | Deterministic implementation spec |
| `flask_rebuild_prompt.md` | Engineered, token-budgeted rebuild prompt |

Other real repos that work well as dogfood: `https://github.com/tiangolo/fastapi.git`,
`https://github.com/django/django.git`.

## 4. The practical mission: customize an OSS repo & get the build prompt

With the API from step 2 running, in a second terminal:

```powershell
# 1) Register the repository
$p = Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/projects `
  -ContentType "application/json" `
  -Body '{"repository_url": "https://github.com/tiangolo/fastapi.git"}'

# 2) Trigger analysis (returns 202; runs in the background queue)
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/projects/$($p.id)/analyze" `
  -ContentType "application/json" -Body '{"branch": "master"}'

# 3) Poll until the analysis is done
while ((Invoke-RestMethod -Uri "http://localhost:8000/api/analysis/$($p.id)").status -ne "done") { Start-Sleep 2 }

# 4) Customize the technology stack (rebinds tech without touching
#    the extracted knowledge: domain, workflows, data model stay stable)
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/projects/$($p.id)/architecture/customize" `
  -ContentType "application/json" `
  -Body '{"backend_technology": "FastAPI", "frontend_technology": "React + TypeScript", "database": "PostgreSQL"}'

# 5) Generate the implementation-ready rebuild prompt (the deliverable)
$r = Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/projects/$($p.id)/implementation-prompt" `
  -ContentType "application/json" -Body '{}'
$r.prompt | Out-File fastapi_rebuild_prompt.md

# 6) Pull the full knowledge package
Invoke-RestMethod -Uri "http://localhost:8000/api/projects/$($p.id)/knowledge" |
  ConvertTo-Json -Depth 6 | Out-File fastapi_knowledge.json
```

`$r.prompt` is a self-contained spec: scaffold order, data model, components
(names/responsibilities/dependencies), API surface, workflows, env contract,
security requirements, and build/verify steps. Pipe it into a frontier coding
model to reconstruct the project.

## 5. Mission tips

- **Auth**: default is `KNOX_AUTH_MODE=none` (dev). For a shared secret, set
  `KNOX_AUTH_MODE=token` and a `KNOX_API_KEY` in `.env`, then add
  `-Headers @{Authorization = "Bearer <key>"}` to every request.
- **Byte-faithful rebuilds (opt-in)**: set `KNOX_LOGIC_CAPTURE_ENABLED=1` in
  `.env` before analyzing so redacted function bodies are embedded in the
  prompt. KNOX's default contract is source -> knowledge (bodies are *not*
  copied); this mode re-materializes them on purpose, with a mandatory warning.
- **Token budget**: tune `KNOX_PROMPT_MAX_TOKENS` in `.env` (default 50000).
  Oversized detail lists are pushed to numbered detail chunks automatically.
- **Logic capture bounds**: `KNOX_LOGIC_CAPTURE_MAX_FUNCTIONS` and
  `KNOX_LOGIC_CAPTURE_MAX_LINES_PER_FUNCTION` keep the package predictable.

## 6. Production / Docker (when you're ready)

```powershell
docker compose up -d --build
```

Full stack: Postgres + Redis + FastAPI + RQ worker + Nginx frontend. The
backend entrypoint runs `alembic upgrade head` on boot. See
`docs/deployment.md` and `docs/runbook.md` for day-2 operations.

## Troubleshooting

- `python -m pytest` fails with `WinError 5 Access denied`: stale pytest temp
  dir. Run `remove-item "$env:LOCALAPPDATA\Temp\pytest-of-HP" -Recurse -Force`.
- SQLite "table projects already exists": delete `backend\data\knox.db` and
  re-run `alembic upgrade head`.
- `401 Unauthorized`: `KNOX_AUTH_MODE=token` but the `Authorization` header
  (or `KNOX_API_KEY`) is missing/empty.
- `429 Rate limit exceeded`: too many requests; wait, or raise
  `KNOX_RATE_LIMIT_REQUESTS`.