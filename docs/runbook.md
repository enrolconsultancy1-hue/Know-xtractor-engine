# KNOX Runbook

Day-2 operations for a running KNOX deployment. Companion to
[`deployment.md`](deployment.md) (how to stand it up) and
[`security.md`](security.md) (threat model).

## Health & monitoring

| Endpoint   | Purpose                                                        |
|------------|----------------------------------------------------------------|
| `/healthz` | Liveness — process is up. Returns `200` always.               |
| `/readyz`  | Readiness — DB reachable and queue backend reachable. `200`/`503`. |
| `/metrics` | Prometheus text format (no external client required).          |

Prometheus metrics emitted: `http_requests_total`, `http_request_duration_seconds`,
`knox_analysis_runs_total`, `knox_analysis_duration_seconds`, `knox_queue_depth`.

Quick checks (single-instance or via the frontend nginx proxy):

```bash
curl -fsS http://localhost:8000/healthz
curl -fsS http://localhost:8000/readyz
curl -fsS http://localhost:8000/metrics | head
```

## Logs

- `KNOX_LOG_FORMAT=text` (default) or `json` for structured logs (one JSON
  object per line, including the `X-Request-ID` correlation id).
- Every response carries an `X-Request-ID` header; the same id appears in the
  access log line for that request, so you can trace a request end-to-end.

```bash
docker compose logs -f backend worker
```

## Starting / stopping

```bash
docker compose up -d --build      # start everything
docker compose ps                 # status
docker compose restart backend    # bounce the API only
docker compose down               # stop (keeps the pgdata volume)
docker compose down -v            # stop AND delete the database volume (destructive)
```

## Running the analysis worker

With `KNOX_QUEUE_BACKEND=rq`, analyses are picked up by the `worker` service:

```bash
docker compose up -d --scale worker=3   # scale workers horizontally
```

Worker health: watch `knox_queue_depth` and `docker compose logs worker`. If a
job never starts, confirm `redis` is healthy and the worker container is running.

## Backups

Postgres (recommended):

```bash
docker compose exec db pg_dump -U knox knox > knox-backup-$(date +%F).sql
# restore:
docker compose exec -T db psql -U knox knox < knox-backup-2026-01-01.sql
```

SQLite (single-node dev only):

```bash
# stop the API first, then copy the file
copy backend\data\knox.db knox.db.bak
```

## Troubleshooting

### `sqlite3.OperationalError: table projects already exists`

Alembic owns the schema. A pre-existing SQLite file created by an older version
of the app conflicts with migrations. Stop the app, delete the stale DB, re-run
`alembic upgrade head`:

```bash
# PowerShell
Remove-Item backend\data\knox.db
# CMD
rmdir /s /q backend\data
```

### Database file is locked (Windows)

Another process still holds the SQLite file — usually a second `uvicorn`
running from an elevated terminal. A normal terminal cannot `taskkill` it
("Access is denied"). Close that terminal window (or use an admin terminal /
Task Manager), then retry.

### `401 Unauthorized` / `503 Service Unavailable`

- `401` → the `Authorization: Bearer <token>` header is missing or wrong.
- `503` with "Auth enabled but KNOX_API_KEY is not configured" →
  `KNOX_AUTH_MODE=token` but the key is unset.

### `429 Rate limit exceeded`

The client exceeded `KNOX_RATE_LIMIT_REQUESTS` within
`KNOX_RATE_LIMIT_WINDOW_SECONDS`. Wait, raise the limit, or set it to `0` to
disable (not recommended for internet-facing deployments).

### Production startup fails fast

In `KNOX_ENVIRONMENT=production`, the app refuses to start if:
- the DB is still SQLite, or
- `KNOX_CORS_ORIGINS` contains `*`, or
- `KNOX_AUTH_MODE=token` without `KNOX_API_KEY`.

Fix the offending env var and restart.

### `pytest` fails with `WinError 5 Access denied`

The OS temp dir (`%LocalAppData%\Temp\pytest-of-HP`) has a broken ACL. The
project already redirects pytest's temp root via `addopts = "--basetemp=.pytest-tmp"`
in `backend/pyproject.toml`. If it recurs, clear the stale dir:

```bash
rmdir /s /q "%LocalAppData%\Temp\pytest-of-HP"
```

## Rotating the API key

1. Generate: `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
2. Update `KNOX_API_KEY` in `.env`.
3. `docker compose up -d` (or restart backend/worker) to pick it up.
4. Update any clients that call the API directly.
