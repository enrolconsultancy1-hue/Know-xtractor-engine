# Security

KNOX analyzes **arbitrary, untrusted repositories**. The threat model assumes a
repository may contain malicious or malformed files.

## What KNOX never does

- Never **executes** repository code — no `pip install`, `npm install`,
  `make`, `setup.py`, shell scripts, or Dockerfiles.
- Never persists **secrets** — env/config values classified as credentials are
  stored only as `SECRET_REQUIRED: <KEY>` placeholders.
- Never allows a repository to **write outside its workspace** — clones land in
  `analysis_workspace/<project_id>/` and path resolution is guarded.

## Controls implemented

| Control | Location |
|---------|----------|
| Repository URL validation (scheme, no local paths, no shell metacharacters) | `services/acquisition.py` |
| Path-traversal guard (`is_within`) | `core/security.py` |
| Secret key classification + value redaction | `core/security.py`, `analyzers/config_analyzer.py` |
| `.gitignore` + default-ignore support | `analyzers/inventory.py` |
| Binary-file detection | `analyzers/inventory.py` |
| Per-file and total-file limits | `core/config.py` |
| Clone timeout | `core/config.py` |
| Analyzer-level exception isolation (one bad file ≠ failed run) | `services/pipeline.py` |
| Network clone toggle (`KNOX_ALLOW_NETWORK_CLONE`) | `core/config.py` |

## Recommendations for production

- Run analysis in a **sandboxed container** (the pipeline is transport-agnostic).
- Replace the in-process thread runner with a queue (Celery/RQ) under resource limits.
- Add rate limiting and authentication in front of the API.
- Keep the AI provider disabled unless you control the vendor and prompt scope.
- Treat `analysis_workspace/` as volatile and never serve it over the API.

## Reporting

Security issues should be reported privately to the repository owner. Do not
open public issues containing exploit details.
