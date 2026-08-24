"""Tests for the operator CLI (help + doctor)."""

from __future__ import annotations

import pytest

from app.cli import main


def test_help_prints_numbered_steps(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["help"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Step-by-step" in out
    for expected in (
        "1. Install Python 3.11+ and Git",
        "python -m app.cli doctor",
        "uvicorn app.main:app --reload --port 8000",
        "docker compose up --build",
    ):
        assert expected in out


def test_default_command_shows_help(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main([])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Step-by-step" in out


def test_doctor_all_green_on_prepared_dev_machine(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # conftest points the runtime dirs at a temp location; create the schema so
    # the migration check passes.
    from app.db import Base, engine

    Base.metadata.create_all(bind=engine)
    rc = main(["doctor"])
    out = capsys.readouterr().out
    assert "Python" in out
    assert "[OK] database reachable" in out
    assert "[FAIL]" not in out, out
    assert rc == 0


def test_doctor_reports_missing_migrations(monkeypatch: pytest.MonkeyPatch,
                                           capsys: pytest.CaptureFixture[str]) -> None:
    """A reachable DB without tables must fail with a concrete fix hint."""
    import sqlalchemy as sa

    class _NoTables:
        def get_table_names(self) -> list[str]:
            return []

    monkeypatch.setattr(sa, "inspect", lambda _engine: _NoTables())
    rc = main(["doctor"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "migrations applied" in out
    assert "alembic upgrade head" in out
