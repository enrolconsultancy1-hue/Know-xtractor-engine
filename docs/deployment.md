# KNOX Deployment

Production deployment with Docker Compose: Postgres + Redis + FastAPI backend +
RQ worker + Nginx-served React frontend, fronted by Caddy for automatic HTTPS.

## Prerequisites

- Docker Engine + Docker Compose v2.
- A domain name (for HTTPS) with DNS pointing at the host.
- Ports `80`/`443` (Caddy) and optionally `8000`/`8080` reachable.

## 1. Configure secrets

```bash
cp .env.example .env
# edit .env:
#   POSTGRES_PASSWORD — URL-safe, no @ : /
#   KNOX_API_KEY       — python -c "import secrets; print(secrets.token_urlsafe(32))"
```

`.env` is gitignored and never committed.

## 2. Start the stack

```bash
docker compose up -d --build
docker compose ps
```

The backend entrypoint runs `alembic upgrade head` before serving, so schema
migrations apply automatically on boot.

## 3. HTTPS reverse proxy (Caddy)

`deploy/Caddyfile` provides automatic Let's Encrypt TLS + security headers.
Edit the domain, then run Caddy in front of the compose network:

```bash
docker run -d --name caddy --network knox_default \
  -p 80:80 -p 443:443 \
  -v "$PWD/deploy/Caddyfile:/etc/caddy/Caddyfile" \
  -v caddy_data:/data caddy:2
```

(A compose service can be added instead; the key contract is
`reverse_proxy frontend:80`.) The frontend nginx proxies `/api`, `/healthz`,
`/readyz`, and `/metrics` to `backend:8000`, so the whole app is same-origin
behind Caddy.

## Services

| Service    | Role                                                        |
|------------|-------------------------------------------------------------|
| `db`       | Postgres 16 (persistent `pgdata` volume).                   |
| `redis`    | Redis 7, message broker for the RQ worker pool.             |
| `backend`  | FastAPI API; runs `alembic upgrade head` then uvicorn on `:8000`. |
| `worker`   | RQ worker (`python -m app.worker`); scale horizontally.      |
| `frontend` | React build served by Nginx with SPA fallback + `/api` proxy. |

## Environment variables

See [`backend/.env.example`](../backend/.env.example) for the full reference.
The critical production settings are:

| Variable                        | Production value                                              |
|---------------------------------|--------------------------------------------------------------|
| `KNOX_ENVIRONMENT`              | `production` (enables fail-fast validation)                  |
| `KNOX_DATABASE_URL`             | `postgresql+psycopg://knox:...@db:5432/knox`                 |
| `KNOX_QUEUE_BACKEND`            | `rq`                                                         |
| `KNOX_REDIS_URL`                | `redis://redis:6379/0`                                       |
| `KNOX_AUTH_MODE` / `KNOX_API_KEY` | `token` + a strong random key                              |
| `KNOX_CORS_ORIGINS`             | `[]` when same-origin behind the proxy                       |
| `KNOX_LOG_FORMAT`               | `json` for structured logs                                   |
| `KNOX_RATE_LIMIT_REQUESTS`      | e.g. `60` (0 disables)                                       |

`KNOX_ENVIRONMENT=production` fails fast if the DB is SQLite, CORS is `*`, or
token auth is enabled without a key.

## Scaling

Analysis is CPU/IO-bound and isolated in workers:

```bash
docker compose up -d --scale worker=3
```

The API is stateless (state lives in Postgres/Redis), so the `backend` service
can also be scaled behind the proxy. Note: the built-in rate limiter is
in-memory (per-process) — for multi-instance API deployments, replace it with a
Redis-backed limiter.

## Security checklist

- [ ] Strong, unique `POSTGRES_PASSWORD` and `KNOX_API_KEY` in `.env`.
- [ ] `KNOX_ENVIRONMENT=production`.
- [ ] HTTPS via Caddy (never expose `:8000` publicly).
- [ ] Rate limiting enabled (non-zero `KNOX_RATE_LIMIT_REQUESTS`).
- [ ] Backups scheduled (`pg_dump`; see [`runbook.md`](runbook.md)).
- [ ] `pip-audit` / `npm audit` green (see CI below).

## CI/CD

`.github/workflows/ci.yml` runs on every push/PR:

- **Backend**: `ruff` (lint) + `mypy` (types) + `pytest --cov=app --cov-fail-under=70`.
- **Frontend**: `npm ci` + `tsc`/Vite build + `npm audit --audit-level=high`.
- **Security**: `pip-audit` against `requirements.txt` + `requirements-dev.txt`.

## First-run verification

```bash
docker compose exec backend python -m pytest -q        # test suite inside the image
curl -fsS http://localhost:8080/healthz                # via frontend proxy
curl -fsS http://localhost:8080/metrics | head         # metrics via proxy
```
