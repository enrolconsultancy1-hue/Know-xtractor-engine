"""Tests for repository acquisition and URL validation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import Settings
from app.services.acquisition import (
    AcquisitionError,
    acquire_repository,
    validate_repo_url,
)


def test_validate_repo_url_valid():
    assert validate_repo_url("https://github.com/user/repo.git") == "https://github.com/user/repo.git"
    assert validate_repo_url("git@github.com:user/repo.git") == "git@github.com:user/repo.git"
    assert validate_repo_url("ssh://git@github.com/user/repo.git") == "ssh://git@github.com/user/repo.git"


def test_validate_repo_url_invalid():
    with pytest.raises(AcquisitionError, match="required"):
        validate_repo_url("")

    with pytest.raises(AcquisitionError, match="unsafe characters"):
        validate_repo_url("https://github.com/user/repo;rm -rf /")

    with pytest.raises(AcquisitionError, match="Invalid repository URL format"):
        validate_repo_url("file:///etc/passwd")

    with pytest.raises(AcquisitionError, match="Invalid repository URL format"):
        validate_repo_url("ftp://server/repo")


def test_acquire_disabled_network_clone(tmp_path: Path):
    with patch("app.services.acquisition.get_settings") as mock_settings:
        mock_settings.return_value = Settings(allow_network_clone=False)
        with pytest.raises(AcquisitionError, match="Network cloning is disabled"):
            acquire_repository("https://github.com/user/repo.git", tmp_path)


def test_acquire_reuses_existing_clone(tmp_path: Path):
    target = tmp_path / "repo"
    (target / ".git").mkdir(parents=True)

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        res = acquire_repository("https://github.com/user/repo.git", tmp_path, branch="main")
        assert res == target
        assert mock_run.call_count == 2  # fetch and checkout


def test_acquire_clone_failure(tmp_path: Path):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stderr="not found")
        with pytest.raises(AcquisitionError, match="Clone failed"):
            acquire_repository("https://github.com/user/repo.git", tmp_path)
