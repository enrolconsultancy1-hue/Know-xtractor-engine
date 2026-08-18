"""Repository acquisition: safe clone into an isolated workspace."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from app.core.config import get_settings
from app.core.security import sanitize_path_segment

_GIT_URL_RE = re.compile(
    r"^(https?://|git@|ssh://git@)?[\w.\-]+[:/][\w.\-]+/[\w.\-]+(\.git)?$"
)


class AcquisitionError(Exception):
    """Raised when a repository cannot be safely acquired."""


def validate_repo_url(url: str) -> str:
    """Validate and normalize a repository URL; reject suspicious input."""
    url = (url or "").strip()
    if not url:
        raise AcquisitionError("Repository URL is required")
    if url.startswith("--") or "|" in url or ";" in url or "$(" in url or "`" in url:
        raise AcquisitionError("Repository URL contains unsafe characters")
    if not _GIT_URL_RE.match(url):
        raise AcquisitionError("Invalid repository URL format")
    if not url.startswith(("https://", "http://", "git@", "ssh://")):
        raise AcquisitionError("Unsupported URL scheme (use https/git/ssh)")
    # Only allow https/http/git/ssh clones; never local paths or file://.
    if url.startswith(("file://", "/", "C:", "\\")):
        raise AcquisitionError("Local paths are not accepted; provide a remote URL")
    return url


def acquire_repository(url: str, workspace: Path, branch: str = "main", commit_ref: str | None = None) -> Path:
    """Clone (or reuse) a repository into an isolated workspace directory."""
    settings = get_settings()
    if not settings.allow_network_clone:
        raise AcquisitionError("Network cloning is disabled in configuration")

    url = validate_repo_url(url)
    branch = sanitize_path_segment(branch or "main")
    workspace.mkdir(parents=True, exist_ok=True)

    slug = sanitize_path_segment(url.rstrip("/").split("/")[-1].removesuffix(".git") or "repo")
    target = workspace / slug

    args: list[str] = ["git", "clone", "--depth", "50", "--single-branch"]
    if commit_ref:
        args += ["--branch", sanitize_path_segment(commit_ref)]
    else:
        args += ["--branch", branch]
    args += [url, str(target)]

    if target.exists() and (target / ".git").exists():
        # Reuse existing clone: fetch and reset instead of re-cloning.
        subprocess.run(
            ["git", "-C", str(target), "fetch", "--depth", "50", "origin", branch],
            capture_output=True, text=True, timeout=settings.clone_timeout_seconds,
        )
        subprocess.run(
            ["git", "-C", str(target), "checkout", branch],
            capture_output=True, text=True, timeout=settings.clone_timeout_seconds,
        )
        return target

    result = subprocess.run(
        args, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=settings.clone_timeout_seconds,
    )
    if result.returncode != 0:
        # Fallback: clone default branch (some repos lack the requested branch name).
        result = subprocess.run(
            ["git", "clone", "--depth", "50", url, str(target)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=settings.clone_timeout_seconds,
        )
        if result.returncode != 0:
            raise AcquisitionError(f"Clone failed: {result.stderr.strip()[:500]}")
    if not (target / ".git").exists():
        raise AcquisitionError("Clone produced no git metadata")
    return target
