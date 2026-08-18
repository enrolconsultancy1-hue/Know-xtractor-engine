# KNOX API Reference

Base URL: `http://localhost:8000/api`

## Projects

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/projects` | Create a project |
| `GET` | `/projects` | List projects |
| `GET` | `/projects/{id}` | Get a project (with runs) |
| `POST` | `/projects/{id}/analyze` | Start analysis (async) |
| `POST` | `/projects/{id}/reanalyze` | Re-run analysis |
| `POST` | `/projects/{id}/cancel` | Cancel a running analysis |

### Create project

```json
POST /projects
{ "repository_url": "https://github.com/owner/repo.git", "name": "repo", "branch": "main" }
```

### Start analysis

```json
POST /projects/1/analyze
{ "branch": "main", "commit_ref": null, "analysis_depth": 3 }
→ { "analysis_id": 7, "status": "started" }
```

## Analysis

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/analysis/{id}` | Status, stage, progress, summary |
| `GET` | `/analysis/{id}/events` | Stage-by-stage progress events |

## Knowledge

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/projects/{id}/knowledge` | Full knowledge package (JSON) |
| `GET` | `/projects/{id}/architecture` | Architecture report |
| `GET` | `/projects/{id}/components` | Components |
| `GET` | `/projects/{id}/workflows` | Workflows |
| `GET` | `/projects/{id}/technologies` | Technology stack |
| `GET` | `/projects/{id}/sprints` | Architectural sprints |
| `GET` | `/projects/{id}/graph` | Knowledge graph (nodes/edges) |

## Architecture

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/projects/{id}/architecture/customize` | Apply technology substitutions |
| `POST` | `/projects/{id}/implementation-prompt` | Generate the single prompt |
| `POST` | `/projects/{id}/export?fmt=markdown` | Export (`json`/`yaml`/`markdown`) |

### Customize

```json
POST /projects/1/architecture/customize
{ "backend_technology": "Django", "database": "PostgreSQL", "frontend_technology": "Flutter" }
```

### Implementation prompt

```json
POST /projects/1/implementation-prompt
{ "backend_technology": "Django" }
→ { "project": "repo", "prompt": "IMPLEMENT THIS ARCHITECTURE\n..." }
```

## Health

`GET /api/health` → `{ "status": "ok", "app": "KNOX", "version": "0.1.0" }`
