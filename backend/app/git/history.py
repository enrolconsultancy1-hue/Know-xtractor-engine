"""Git history extraction via the `git` CLI (no code execution of the repo)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from app.domain.sprint import CommitInfo


class GitHistory:
    """Reads commit history from a cloned repository's .git metadata."""

    def __init__(self, repo_path: str | Path) -> None:
        self.repo_path = Path(repo_path)
        self.is_repo = (self.repo_path / ".git").exists()

    def _run(self, args: list[str]) -> str:
        result = subprocess.run(
            ["git", "-C", str(self.repo_path), *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        return result.stdout

    def commits(self, limit: int = 2000) -> list[CommitInfo]:
        if not self.is_repo:
            return []
        out = self._run([
            "log", "--date=iso-strict", f"-{limit}",
            "--pretty=format:%H%x1f%h%x1f%an%x1f%ad%x1f%s",
        ])
        commits: list[CommitInfo] = []
        for line in out.splitlines():
            parts = line.split("\x1f")
            if len(parts) < 5:
                continue
            sha, short, author, timestamp, message = parts[0], parts[1], parts[2], parts[3], "\x1f".join(parts[4:])
            commits.append(CommitInfo(
                sha=sha, short_sha=short, message=message, author=author, timestamp=timestamp,
            ))
        return commits

    def files_changed(self, sha: str) -> list[str]:
        if not self.is_repo:
            return []
        out = self._run(["show", "--name-only", "--pretty=format:", sha])
        return [line.strip() for line in out.splitlines() if line.strip()]

    def branches(self) -> list[str]:
        if not self.is_repo:
            return []
        return [b.strip() for b in self._run(["branch", "-a"]).splitlines() if b.strip()]

    def tags(self) -> list[str]:
        if not self.is_repo:
            return []
        return [t.strip() for t in self._run(["tag"]).splitlines() if t.strip()]
