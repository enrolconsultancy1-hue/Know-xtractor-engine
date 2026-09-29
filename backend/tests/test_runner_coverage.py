"""Comprehensive tests for app.services.runner – targeting all uncovered branches."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services import runner as runner_mod
from app.services.runner import (
    _emit,
    _finish,
    _persist_progress,
    _update,
    cancel_analysis,
    execute_analysis,
    load_package,
    package_path,
    run_state,
    run_task,
    start_analysis,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_run(run_id=1, status="pending", stage="init", progress=0.0):
    run = MagicMock()
    run.id = run_id
    run.status = status
    run.stage = stage
    run.progress = progress
    run.errors = []
    run.warnings = []
    run.summary = {}
    return run


def _make_db(run=None):
    db = MagicMock()
    db.get.return_value = run
    return db


# ---------------------------------------------------------------------------
# run_state – in-process
# ---------------------------------------------------------------------------

class TestRunStateInProcess:
    def setup_method(self):
        runner_mod._runs.clear()

    def test_unknown_run(self):
        state = run_state(9999)
        assert state["status"] == "unknown"

    def test_known_run(self):
        runner_mod._runs[42] = {"status": "running", "stage": "analysis", "progress": 0.5,
                                "errors": [], "warnings": [], "events": []}
        state = run_state(42)
        assert state["status"] == "running"

    def test_returns_copy(self):
        runner_mod._runs[1] = {"status": "done", "stage": "done", "progress": 1.0}
        state = run_state(1)
        state["status"] = "mutated"
        assert runner_mod._runs[1]["status"] == "done"


# ---------------------------------------------------------------------------
# run_state – RQ branch
# ---------------------------------------------------------------------------

class TestRunStateRQ:
    def test_rq_unknown_run(self):
        db = _make_db(run=None)
        with (
            patch("app.services.runner.get_settings") as ms,
            patch("app.services.runner.SessionLocal", return_value=db),
        ):
            ms.return_value.queue_backend = "rq"
            state = run_state(999)
        assert state["status"] == "unknown"

    def test_rq_known_run(self):
        run = _make_run(run_id=5, status="done", stage="done", progress=1.0)
        run.errors = ["e"]
        run.warnings = ["w"]
        run.summary = {"files": 10}
        db = _make_db(run=run)
        with (
            patch("app.services.runner.get_settings") as ms,
            patch("app.services.runner.SessionLocal", return_value=db),
        ):
            ms.return_value.queue_backend = "rq"
            state = run_state(5)
        assert state["status"] == "done"
        assert state["errors"] == ["e"]
        db.close.assert_called_once()


# ---------------------------------------------------------------------------
# _update / _emit
# ---------------------------------------------------------------------------

class TestUpdateEmit:
    def setup_method(self):
        runner_mod._runs.clear()

    def test_update_creates_state(self):
        _update(10, status="running")
        assert runner_mod._runs[10]["status"] == "running"

    def test_emit_appends_event(self):
        _update(20, events=[])
        _emit(20, "stage_a", 0.1, "Starting")
        assert len(runner_mod._runs[20]["events"]) == 1
        assert runner_mod._runs[20]["events"][0]["pct"] == 0.1

    def test_emit_auto_creates_events_list(self):
        runner_mod._runs[30] = {"status": "pending", "stage": "", "progress": 0.0}
        _emit(30, "init", 0.0, "Hello")
        assert runner_mod._runs[30]["events"]


# ---------------------------------------------------------------------------
# _persist_progress / _finish
# ---------------------------------------------------------------------------

class TestPersistAndFinish:
    def setup_method(self):
        runner_mod._runs.clear()

    def test_persist_updates_run(self):
        run = _make_run(run_id=1)
        db = _make_db(run=run)
        _persist_progress(db, 1, "analysis", 0.5)
        assert run.stage == "analysis"
        db.commit.assert_called_once()

    def test_persist_noop_when_no_run(self):
        db = _make_db(run=None)
        _persist_progress(db, 99, "s", 0.5)
        db.commit.assert_not_called()

    def test_finish_sets_all_fields(self):
        runner_mod._runs[1] = {"status": "running", "stage": "x", "progress": 0.5,
                               "errors": [], "warnings": [], "events": []}
        run = _make_run(run_id=1)
        db = _make_db(run=run)
        with patch("app.services.runner.metrics") as mm:
            mm.knox_analysis_runs_total = MagicMock()
            mm.knox_analysis_duration_seconds = MagicMock()
            _finish(db, 1, "done", summary={"f": 1}, errors=[], warnings=["w"])
        assert run.status == "done"
        assert run.warnings == ["w"]

    def test_finish_records_duration_when_started(self):
        runner_mod._runs[2] = {"status": "running", "stage": "x", "progress": 0.1,
                               "errors": [], "warnings": [], "events": [],
                               "started_monotonic": 0.0}
        run = _make_run(run_id=2)
        db = _make_db(run=run)
        with patch("app.services.runner.metrics") as mm:
            mm.knox_analysis_runs_total = MagicMock()
            mm.knox_analysis_duration_seconds = MagicMock()
            _finish(db, 2, "done")
        mm.knox_analysis_duration_seconds.observe.assert_called_once()

    def test_finish_skips_duration_when_no_start(self):
        runner_mod._runs[3] = {"status": "running", "stage": "x", "progress": 0.1,
                               "errors": [], "warnings": [], "events": []}
        run = _make_run(run_id=3)
        db = _make_db(run=run)
        with patch("app.services.runner.metrics") as mm:
            mm.knox_analysis_runs_total = MagicMock()
            mm.knox_analysis_duration_seconds = MagicMock()
            _finish(db, 3, "failed", errors=["err"])
        mm.knox_analysis_duration_seconds.observe.assert_not_called()

    def test_finish_noop_when_no_run(self):
        runner_mod._runs[4] = {"status": "r", "stage": "", "progress": 0.0,
                               "errors": [], "warnings": [], "events": []}
        db = _make_db(run=None)
        with patch("app.services.runner.metrics") as mm:
            mm.knox_analysis_runs_total = MagicMock()
            mm.knox_analysis_duration_seconds = MagicMock()
            _finish(db, 4, "done")
        db.commit.assert_not_called()


# ---------------------------------------------------------------------------
# start_analysis
# ---------------------------------------------------------------------------

class TestStartAnalysis:
    def setup_method(self):
        runner_mod._runs.clear()

    def test_start_inprocess(self):
        session = MagicMock()
        def _fake_add(obj):
            obj.id = 7
        session.add.side_effect = _fake_add
        with (
            patch("app.services.runner.get_settings") as ms,
            patch("app.services.runner.default_queue") as mq,
        ):
            ms.return_value.queue_backend = "inprocess"
            run_id = start_analysis(1, "https://github.com/org/repo.git", session=session)
        assert run_id == 7
        mq.submit.assert_called_once()

    def test_start_without_session_creates_one(self):
        fake_session = MagicMock()
        def _fake_add(obj):
            obj.id = 9
        fake_session.add.side_effect = _fake_add
        with (
            patch("app.services.runner.get_settings") as ms,
            patch("app.services.runner.SessionLocal", return_value=fake_session),
            patch("app.services.runner.default_queue"),
        ):
            ms.return_value.queue_backend = "inprocess"
            run_id = start_analysis(1, "https://github.com/org/repo.git")
        assert run_id == 9
        fake_session.close.assert_called_once()


# ---------------------------------------------------------------------------
# run_task
# ---------------------------------------------------------------------------

class TestRunTask:
    def test_delegates_to_execute_analysis(self):
        task = {"project_id": 1, "url": "https://g.com/r.git", "branch": "main", "commit_ref": None}
        with patch("app.services.runner.execute_analysis") as me:
            run_task(task, 99)
        me.assert_called_once_with(1, "https://g.com/r.git", "main", None, 99, None)


# ---------------------------------------------------------------------------
# execute_analysis – error paths
# ---------------------------------------------------------------------------

class TestExecuteAnalysis:
    def setup_method(self):
        runner_mod._runs.clear()

    def _init_run(self, run_id):
        runner_mod._runs[run_id] = {"status": "running", "stage": "", "progress": 0.0,
                                    "errors": [], "warnings": [], "events": []}

    def test_acquisition_failure(self):
        run = _make_run(run_id=1)
        db = _make_db(run=run)
        self._init_run(1)
        from app.services.acquisition import AcquisitionError
        with (
            patch("app.services.runner.SessionLocal", return_value=db),
            patch("app.services.runner.get_settings") as ms,
            patch("app.services.runner.acquire_repository", side_effect=AcquisitionError("bad")),
            patch("app.services.runner.metrics") as mm,
        ):
            ms.return_value.workspace_dir = MagicMock()
            ms.return_value.analysis_timeout_seconds = 60
            mm.knox_analysis_runs_total = MagicMock()
            mm.knox_analysis_duration_seconds = MagicMock()
            execute_analysis(1, "https://bad.com/r.git", "main", None, 1, None)
        assert run.status == "failed"

    def test_timeout_failure(self):
        run = _make_run(run_id=2)
        db = _make_db(run=run)
        self._init_run(2)
        fake_future = MagicMock()
        fake_future.result.side_effect = TimeoutError
        with (
            patch("app.services.runner.SessionLocal", return_value=db),
            patch("app.services.runner.get_settings") as ms,
            patch("app.services.runner.acquire_repository", return_value=MagicMock()),
            patch("app.services.runner.AnalysisPipeline"),
            patch("app.services.runner.PipelineContext"),
            patch("concurrent.futures.ThreadPoolExecutor") as mex,
            patch("app.services.runner.metrics") as mm,
        ):
            ms.return_value.workspace_dir = MagicMock()
            ms.return_value.analysis_timeout_seconds = 1
            mm.knox_analysis_runs_total = MagicMock()
            mm.knox_analysis_duration_seconds = MagicMock()
            mex.return_value.__enter__ = lambda s: s
            mex.return_value.__exit__ = MagicMock(return_value=False)
            mex.return_value.submit.return_value = fake_future
            execute_analysis(1, "https://g.com/r.git", "main", None, 2, None)
        assert run.status == "failed"
        assert any("timed out" in e for e in run.errors)

    def test_pipeline_exception(self):
        run = _make_run(run_id=3)
        db = _make_db(run=run)
        self._init_run(3)
        fake_future = MagicMock()
        fake_future.result.side_effect = RuntimeError("boom")
        with (
            patch("app.services.runner.SessionLocal", return_value=db),
            patch("app.services.runner.get_settings") as ms,
            patch("app.services.runner.acquire_repository", return_value=MagicMock()),
            patch("app.services.runner.AnalysisPipeline"),
            patch("app.services.runner.PipelineContext") as mc,
            patch("concurrent.futures.ThreadPoolExecutor") as mex,
            patch("app.services.runner.metrics") as mm,
        ):
            ci = MagicMock()
            ci.errors = []
            ci.warnings = []
            mc.return_value = ci

            ms.return_value.workspace_dir = MagicMock()
            ms.return_value.analysis_timeout_seconds = 60
            mm.knox_analysis_runs_total = MagicMock()
            mm.knox_analysis_duration_seconds = MagicMock()
            mex.return_value.__enter__ = lambda s: s
            mex.return_value.__exit__ = MagicMock(return_value=False)
            mex.return_value.submit.return_value = fake_future
            execute_analysis(1, "https://g.com/r.git", "main", None, 3, None)
        assert run.status == "failed"

    def test_cancel_after_pipeline(self):
        run = _make_run(run_id=4)
        db = _make_db(run=run)
        self._init_run(4)
        fake_pkg = MagicMock()
        fake_pkg.stats.return_value = {"files": 1}
        fake_future = MagicMock()
        fake_future.result.return_value = fake_pkg
        job = MagicMock()
        job.cancel_requested = True
        with (
            patch("app.services.runner.SessionLocal", return_value=db),
            patch("app.services.runner.get_settings") as ms,
            patch("app.services.runner.acquire_repository", return_value=MagicMock()),
            patch("app.services.runner.AnalysisPipeline"),
            patch("app.services.runner.PipelineContext") as mc,
            patch("concurrent.futures.ThreadPoolExecutor") as mex,
            patch("app.services.runner.metrics") as mm,
        ):
            ci = MagicMock()
            ci.errors = []
            ci.warnings = []
            mc.return_value = ci

            ms.return_value.workspace_dir = MagicMock()
            ms.return_value.analysis_timeout_seconds = 60
            ms.return_value.packages_dir = MagicMock()
            ms.return_value.exports_dir = MagicMock()
            mm.knox_analysis_runs_total = MagicMock()
            mm.knox_analysis_duration_seconds = MagicMock()
            mex.return_value.__enter__ = lambda s: s
            mex.return_value.__exit__ = MagicMock(return_value=False)
            mex.return_value.submit.return_value = fake_future
            execute_analysis(1, "https://g.com/r.git", "main", None, 4, job)
        assert run.status == "cancelled"

    def test_happy_path_done(self):
        run = _make_run(run_id=5)
        db = _make_db(run=run)
        self._init_run(5)
        fake_pkg = MagicMock()
        fake_pkg.model_dump_json.return_value = '{"data": 1}'
        fake_pkg.stats.return_value = {"files": 5}
        fake_future = MagicMock()
        fake_future.result.return_value = fake_pkg
        mock_pkg_path = MagicMock()
        with (
            patch("app.services.runner.SessionLocal", return_value=db),
            patch("app.services.runner.get_settings") as ms,
            patch("app.services.runner.acquire_repository", return_value=MagicMock()),
            patch("app.services.runner.AnalysisPipeline"),
            patch("app.services.runner.PipelineContext") as mc,
            patch("concurrent.futures.ThreadPoolExecutor") as mex,
            patch("app.services.runner.export_package"),
            patch("app.services.runner.metrics") as mm,
        ):
            ci = MagicMock()
            ci.errors = []
            ci.warnings = []
            mc.return_value = ci

            ms.return_value.workspace_dir = MagicMock()
            ms.return_value.analysis_timeout_seconds = 60
            ms.return_value.packages_dir = MagicMock()
            ms.return_value.packages_dir.__truediv__ = MagicMock(return_value=mock_pkg_path)
            ms.return_value.exports_dir = MagicMock()
            mm.knox_analysis_runs_total = MagicMock()
            mm.knox_analysis_duration_seconds = MagicMock()
            mex.return_value.__enter__ = lambda s: s
            mex.return_value.__exit__ = MagicMock(return_value=False)
            mex.return_value.submit.return_value = fake_future
            execute_analysis(1, "https://github.com/org/repo.git", "main", None, 5, None)
        assert run.status == "done"
        mock_pkg_path.write_text.assert_called_once()


# ---------------------------------------------------------------------------
# cancel_analysis
# ---------------------------------------------------------------------------

class TestCancelAnalysis:
    def setup_method(self):
        runner_mod._runs.clear()

    def test_cancel_inprocess(self):
        runner_mod._runs[10] = {"status": "running", "stage": "analysis", "progress": 0.5,
                                "errors": [], "warnings": [], "events": []}
        with (
            patch("app.services.runner.get_settings") as ms,
            patch("app.services.runner.default_queue") as mq,
        ):
            ms.return_value.queue_backend = "inprocess"
            result = cancel_analysis(10)
        assert result is True
        mq.cancel.assert_called_once_with(10)
        assert runner_mod._runs[10]["status"] == "cancelled"

    def test_cancel_rq(self):
        runner_mod._runs[11] = {"status": "running", "stage": "", "progress": 0.0,
                                "errors": [], "warnings": [], "events": []}
        mock_rq = MagicMock()
        with (
            patch("app.services.runner.get_settings") as ms,
            patch.dict("sys.modules", {"app.services.rq_queue": MagicMock(rq_queue=mock_rq)}),
        ):
            ms.return_value.queue_backend = "rq"
            result = cancel_analysis(11)
        assert result is True


# ---------------------------------------------------------------------------
# load_package / package_path
# ---------------------------------------------------------------------------

class TestLoadPackage:
    def test_load_existing(self, tmp_path):
        (tmp_path / "project_1.json").write_text('{"key": "value"}', encoding="utf-8")
        with patch("app.services.runner.get_settings") as ms:
            ms.return_value.packages_dir = tmp_path
            assert load_package(1) == {"key": "value"}

    def test_load_missing(self, tmp_path):
        with patch("app.services.runner.get_settings") as ms:
            ms.return_value.packages_dir = tmp_path
            assert load_package(99) is None

    def test_package_path(self, tmp_path):
        with patch("app.services.runner.get_settings") as ms:
            ms.return_value.packages_dir = tmp_path
            assert package_path(7) == tmp_path / "project_7.json"
