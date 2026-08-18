"""Tests for sprint clustering (pure, no git required)."""

from app.domain.sprint import CommitInfo
from app.git.sprints import cluster_sprints


def _commit(short: str, msg: str, days_ago: int) -> CommitInfo:
    return CommitInfo(
        sha=f"{short}" * 40, short_sha=short, message=msg, author="t",
        timestamp=f"2024-01-{max(1, 20 - days_ago):02d}T12:00:00+00:00",
    )


def test_clusters_related_commits():
    commits = [
        _commit("a", "Initial application skeleton", 20),
        _commit("b", "Add API routes", 19),
        _commit("c", "Add database models", 18),
        _commit("d", "Add authentication", 5),
    ]
    timeline = cluster_sprints(commits)
    # Two time-clusters expected (gap > 5 days).
    assert len(timeline.sprints) >= 2


def test_empty_commits():
    assert cluster_sprints([]).sprints == []
