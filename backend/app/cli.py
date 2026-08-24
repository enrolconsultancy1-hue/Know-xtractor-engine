"""KNOX command-line helper: friendly, step-by-step guidance for operators.

Usage (from the ``backend`` directory)::

    python -m app.cli            # step-by-step install & use guide
    python -m app.cli doctor     # environment health check with fix hints
    python -m app.cli help       # same as the default output

The goal is that a brand-new operator never has to ask "what now?": the help
output is a numbered walkthrough, and ``doctor`` verifies each prerequisite on
the actual machine, printing a concrete fix hint for every failed check.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

# Steps shown by the default help output. Kept in data form so tests can
# assert on them and so they stay in one obvious place to maintain.
_STEPS: list[tuple[str, list[str]]] = [
    ("Install Python 3.11+ and Git", [
        "python --version      # need 3.11 or newer",
        "git --version",
    ]),
    ("Create a virtualenv and install the backend", [
        "cd backend",
        "python -m venv .venv",
        # Windows activation differs from POSIX; show both.
        ".venv\\Scripts\\activate            # Windows",
        "source .venv/bin/activate           # macOS / Linux",
        "pip install -r requirements.txt",
    ]),
    ("Configure the environment (optional in dev)", [
        "copy .env.example .env               # Windows",
        "cp .env.example .env                 # macOS / Linux",
        "# Dev defaults work with zero configuration; edit .env for Postgres,",
        "# auth tokens, queue backend, and analysis limits.",
    ]),
    ("Verify your setup", [
        "python -m app.cli doctor             # every check should print OK",
    ]),
    ("Run migrations and start the API", [
        "alembic upgrade head",
        "uvicorn app.main:app --reload --port 8000",
        "# Open http://127.0.0.1:8000/docs for the interactive API.",
    ]),
    ("Start the web UI", [
        "cd ..\\frontend                       # (cd ../frontend on macOS/Linux)",
        "npm install",
        "npm run dev                          # http://localhost:5173",
    ]),
    ("Analyze your first repository", [
        "# In the web UI: 'New Analysis' -> paste a GitHub URL -> Analyze.",
        "# Or with plain HTTP:",
        'curl -X POST http://127.0.0.1:8000/api/projects '
        '-H "Content-Type: application/json" '
        '-d "{\\"repository_url\\": \\"https://github.com/fastapi/fastapi.git\\"}"',
        "curl -X POST http://127.0.0.1:8000/api/projects/1/analyze "
        '-H "Content-Type: application/json" -d "{\\"branch\\": \\"main\\"}"',
        "# Poll GET /api/analysis/{id} until status == done.",
    ]),
    ("Use the results", [
        "# Repository / Architecture / Knowledge / Sprints pages explore the",
        "# extracted knowledge; 'Implementation' customizes the tech stack and",
        "# 'Prompt' generates the single implementation-ready rebuild prompt.",
    ]),
    ("Production deploy (optional)", [
        "docker compose up --build            # full stack + Postgres + Redis",
        "curl http://localhost:8000/healthz   # should answer {\"status\":\"ok\"}",
        "# See docs/deployment.md and docs/runbook.md for HTTPS and operations.",
    ]),
]

_REQUIRED_PACKAGES = ["fastapi", "uvicorn", "sqlalchemy", "alembic", "pydantic", "yaml"]
_OPTIONAL_PACKAGES = ["tree_sitter", "tree_sitter_language_pack"]


def _print_help() -> None:
    print("KNOX — Knowledge eXtraction & Architectural Reconstruction Engine")
    print("Step-by-step: install, configure, run, analyze.")
    print()
    for i, (title, cmds) in enumerate(_STEPS, start=1):
        print(f"  {i}. {title}")
        for c in cmds:
            print(f"       {c}")
        print()
    print("More help:")
    print("  python -m app.cli doctor     check this machine is ready")
    print("  docs/QUICKSTART.md           clone-to-analysis walkthrough")
    print("  docs/RUNBOOK.md              day-2 operations")
    print("  docs/deployment.md           production deployment")


def _check(label: str, ok: bool, hint: str = "") -> bool:
    mark = "[OK]" if ok else "[FAIL]"
    print(f"  {mark} {label}")
    if not ok and hint:
        print(f"       fix: {hint}")
    return ok


def _check_package(modname: str, required: bool) -> bool:
    try:
        __import__(modname)
    except ImportError:
        return _check(
            f"package '{modname}' importable",
            False,
            hint="pip install -r requirements.txt"
            if required
            else "optional — JS/TS and multi-language parsing disabled without it",
        )
    return _check(f"package '{modname}' importable", True)


def cmd_doctor() -> int:
    """Verify every prerequisite for running KNOX on this machine."""
    failures = 0

    print("KNOX doctor — checking your environment")
    print()

    print("Python & packages")
    v = sys.version_info
    failures += not _check(
        f"Python {'.'.join(map(str, v[:3]))} (need >= 3.11)",
        v >= (3, 11),
        hint="install Python 3.11+ from https://www.python.org/downloads/",
    )
    for pkg in _REQUIRED_PACKAGES:
        failures += not _check_package(pkg, required=True)
    for pkg in _OPTIONAL_PACKAGES:
        _check_package(pkg, required=False)  # optional: never counts as failure
    print()

    print("Configuration")
    if Path(".env").exists():
        _check(".env file present", True)
    else:
        # Not a hard failure: dev defaults need no configuration.
        print("       [warn] no .env file — dev defaults apply; production requires one")
        print("              fix: copy .env.example .env")
    print()

    print("Storage")
    from app.core.config import get_settings

    settings = get_settings()
    settings.ensure_dirs()
    writable = True
    for d in (settings.data_dir, settings.workspace_dir, settings.packages_dir, settings.exports_dir):
        try:
            with tempfile.NamedTemporaryFile(dir=d, delete=True):
                pass
        except OSError as exc:
            writable = False
            failures += not _check(f"'{d}' is writable", False, hint=str(exc))
    if writable:
        _check("runtime directories are writable", True)
    print()

    print("Database")
    try:
        from sqlalchemy import inspect, text

        from app.db import engine

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        tables = set(inspect(engine).get_table_names())
        _check("database reachable", True)
        if not _check(
            "migrations applied ('projects' table found)",
            {"projects", "analysis_runs"} <= tables,
            hint="alembic upgrade head",
        ):
            failures += 1
    except Exception as exc:  # noqa: BLE001 — report any DB problem verbatim
        failures += not _check(
            "database reachable", False,
            hint=f"{type(exc).__name__}: {exc}",
        )
    print()

    print("Queue")
    if settings.queue_backend == "rq":
        try:
            import redis

            conn = redis.from_url(settings.redis_url)
            conn.ping()
            _check("Redis reachable (queue backend: rq)", True)
        except Exception as exc:  # noqa: BLE001
            failures += not _check(
                "Redis reachable (queue backend: rq)", False,
                hint=f"start Redis or keep KNOX_QUEUE_BACKEND=inprocess ({type(exc).__name__})",
            )
    else:
        _check("in-process queue selected (no Redis needed)", True)
    print()

    if failures:
        print(f"{failures} check(s) failed — apply the fixes above, then re-run.")
        return 1
    print("All checks passed. You are ready to run: uvicorn app.main:app --reload")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli",
        description="KNOX operator helper: guided setup and environment checks.",
    )
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("help", help="show the step-by-step install & use guide")
    sub.add_parser("doctor", help="verify this machine is ready to run KNOX")
    args = parser.parse_args(argv)

    if args.command == "doctor":
        return cmd_doctor()
    _print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
