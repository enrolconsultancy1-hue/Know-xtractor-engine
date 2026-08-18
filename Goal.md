# KNOX — Production Readiness Goal

**Objective:** bring KNOX from "working engine" to **100% production-ready** — deployable,
observable, secured, and testable end-to-end from the terminal.

**Status tracker:** each phase has checkboxes. A phase is "done" only when its
Definition of Done (DoD) is satisfied and the terminal test command passes.

---

## Baseline (already complete)

- [x] 12-stage deterministic analysis pipeline (source → knowledge package → architecture → prompt)
- [x] React + TypeScript + Vite frontend (builds clean)
- [x] Tree-sitter JS/TS/TSX/Vue/Svelte analyzer
- [x] Alembic migrations (`migrations/`, `0001_initial`)
- [x] In-process queue with cooperative cancellation (`services/queue.py`)
- [x] Router-prefix resolution + microservices gating (regression-tested)
- [x] `pytest` (38), `ruff`, `mypy` all clean
- [x] Network-clone analysis proven on `pallets/flask`

---

## Phase 1 — Production configuration & secrets management

**Goal:** single source of truth for all runtime settings; safe, validated config.

- [x] `backend/.env.example` with every setting documented
- [x] Required-settings validation (fail fast with a clear message, no silent defaults for prod)
- [x] Postgres support via `KNOX_DATABASE_URL` (psycopg driver) with SQLite as the dev fallback
- [x] CORS allowlist (`KNOX_CORS_ORIGINS`), not `*`
- [x] Resource limits: max repo size, max file size, max files, clone depth, analysis timeout
- [x] Secret redaction: never write secrets into exports/logs (audit + unit test)

**DoD:** `KNOX_DATABASE_URL` pointing at Postgres boots and migrates; `.env.example` is the
complete reference; limits are enforced and tested.

**Terminal test:**
```bash
cd backend
cp .env.example .env            # then edit
pip install -r requirements.txt
alembic upgrade head
python -m pytest -q
uvicorn app.main:app --reload   # http://127.0.0.1:8000/docs
```

---

## Phase 2 — Authentication & authorization

**Goal:** mutations are protected; reads can stay open (self-host) or be protected.

- [x] API-key / bearer-token auth dependency (`app/api/auth.py`)
- [x] Single-tenant token mode (`KNOX_AUTH_MODE=token`); JWT/user scoping documented as a future multi-tenant extension
- [x] Protect create/start/cancel/delete endpoints (delete endpoint added)
- [x] `KNOX_AUTH_MODE` = `none` (dev) | `token` (shared secret); `users` (JWT) deferred
- [x] Tests: 401 on protected routes without token; 200 with token; 204 on delete

**DoD:** with `KNOX_AUTH_MODE=token`, unauthenticated mutation calls return 401;
authenticated calls succeed; dev mode (`none`) is unaffected.

**Terminal test:**
```bash
cd backend
KNOX_AUTH_MODE=token KNOX_API_KEY=secret uvicorn app.main:app --port 8000
curl -i http://127.0.0.1:8000/api/health
curl -i -X POST http://127.0.0.1:8000/api/projects   # expect 401
curl -i -X POST http://127.0.0.1:8000/api/projects -H "Authorization: Bearer secret"
```

---

## Phase 3 — Production queue & workers

**Goal:** scale analysis to multiple processes; keep dev simple.

- [x] `RQQueue` adapter (Redis/RQ) in `app/services/rq_queue.py`
- [x] Worker entrypoint `app/worker.py` with retry (max 3) + job timeout
- [x] `KNOX_QUEUE_BACKEND` = `inprocess` (default, no Redis) | `rq` (opt-in)
- [x] Tests: backend selection + worker import; RQ roundtrip skips without Redis

**DoD:** `KNOX_QUEUE_BACKEND=rq` + a Redis server runs analyses via `python -m app.worker`;
`inprocess` still works with no Redis installed.

**Terminal test:**
```bash
cd backend
# dev (no Redis): uvicorn app.main:app  -> uses in-process queue
# prod (Redis):  docker run -d -p 6379:6379 redis:7
KNOX_QUEUE_BACKEND=rq python -m app.worker
```

---

## Phase 4 — Observability & reliability

**Goal:** you can see and trust what the service is doing.

- [x] Structured JSON logging option (`KNOX_LOG_FORMAT=json`)
- [x] Prometheus metrics endpoint (`/metrics`) — requests, analysis duration, queue depth
- [x] Liveness `/healthz` and readiness `/readyz` (DB + queue check)
- [x] Clone/analysis timeouts + stale-workspace cleanup
- [x] Request correlation IDs

**DoD:** `/metrics` and `/readyz` respond; timeouts cancel long clones; logs are JSON when set.

**Terminal test:**
```bash
cd backend
KNOX_LOG_FORMAT=json uvicorn app.main:app --port 8000
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8000/readyz
curl http://127.0.0.1:8000/metrics
```

---

## Phase 5 — Containerization & deployment

**Goal:** one-command deploy.

- [x] `backend/Dockerfile` (slim python, non-root, pinned deps)
- [x] `frontend/Dockerfile` (node build → nginx static, or backend-served)
- [x] `docker-compose.yml` (app + postgres + redis + proxy)
- [x] Caddy/nginx reverse proxy config with HTTPS
- [x] Entrypoint runs `alembic upgrade head` then starts the app

**DoD:** `docker compose up` brings up the full stack; `/healthz` is green through the proxy.

**Terminal test:**
```bash
docker compose up --build
curl https://localhost/healthz   # or http://localhost:8000/healthz
```

---

## Phase 6 — CI/CD

**Goal:** every change is gated automatically.

- [x] `.github/workflows/ci.yml` — pytest + ruff + mypy + frontend build
- [x] Coverage gate (e.g. `pytest --cov` with a floor)
- [x] Dependency audit (pip-audit, npm audit) in CI
- [ ] (optional) Docker image build/push job — not implemented (optional)

**DoD:** a PR that breaks tests/lint/types/build is blocked.

**Terminal test (local equivalent of CI):**
```bash
cd backend && pytest -q && ruff check . && mypy app
cd ../frontend && npm run build
```

---

## Phase 7 — Security hardening & final acceptance

**Goal:** untrusted-repo safety and a clean acceptance pass.

- [x] Secret redaction across all exports/logs (sweep + test)
- [x] Path-traversal / symlink guards on untrusted repo content (zip-slip N/A: no archive extraction)
- [x] Rate limiting on analysis/clone endpoints
- [x] Dependency audit wired in CI (pip-audit + npm audit)
- [x] Final dogfood: analyze a large real repo end-to-end (tiangolo/fastapi)
- [x] Runbook + deployment guide (`docs/runbook.md`, `docs/deployment.md`)

**DoD:** full suite green; security audit items resolved; runbook lets a new operator run it.

**Terminal test:**
```bash
cd backend && python analyze_remote.py https://github.com/tiangolo/fastapi.git main
```

---

## Definition of "100% production ready"

All phases 1–7 checked, full test suite green, `ruff` + `mypy` clean, frontend builds,
`docker compose up` serves a working instance, and a fresh operator can run it from
`docs/RUNBOOK.md` without asking questions.
