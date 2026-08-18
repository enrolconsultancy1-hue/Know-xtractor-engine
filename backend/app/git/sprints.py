"""Architectural sprint clustering from raw commit history.

Sprints are meaningful evolutions, not individual commits. We cluster commits
by (a) time gaps, (b) commit-message topics, and (c) changed file paths.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime

from app.domain.common import Confidence, Evidence
from app.domain.sprint import ArchitecturalSprint, CommitInfo, EvolutionTimeline

_TOPIC_KEYWORDS: dict[str, list[str]] = {
    "API layer": ["api", "endpoint", "route", "controller", "handler", "rest", "graphql"],
    "Database / persistence": ["database", "db", "migration", "model", "schema", "repository", "sql", "orm"],
    "Authentication": ["auth", "login", "jwt", "token", "oauth", "session", "password"],
    "Frontend / UI": ["ui", "frontend", "react", "component", "css", "style", "page", "view"],
    "Background processing": ["worker", "queue", "job", "celery", "async", "task", "cron"],
    "Deployment / infrastructure": ["deploy", "docker", "kubernetes", "ci", "cd", "aws", "infra", "terraform"],
    "Testing": ["test", "spec", "fixture", "coverage", "mock"],
    "Documentation": ["doc", "readme", "docs", "comment"],
    "Configuration": ["config", "setting", "env", "setup"],
    "Refactoring": ["refactor", "cleanup", "rename", "move", "extract", "lint"],
}


def _topic_of(message: str, files: list[str]) -> str:
    text = (message + " " + " ".join(files)).lower()
    scores: dict[str, int] = {}
    for topic, keywords in _TOPIC_KEYWORDS.items():
        scores[topic] = sum(1 for k in keywords if k in text)
    best = max(scores.items(), key=lambda kv: kv[1])
    return best[0] if best[1] > 0 else "General development"


def _parse_ts(iso: str) -> datetime:
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return datetime(1970, 1, 1)


def cluster_sprints(commits: list[CommitInfo], time_gap_hours: int = 120) -> EvolutionTimeline:
    """Cluster commits into architectural sprints."""
    timeline = EvolutionTimeline()
    if not commits:
        return timeline

    # Sort oldest-first.
    ordered = sorted(commits, key=lambda c: _parse_ts(c.timestamp))

    clusters: list[list[CommitInfo]] = []
    current: list[CommitInfo] = []
    prev_ts: datetime | None = None
    for c in ordered:
        ts = _parse_ts(c.timestamp)
        if prev_ts is not None and (ts - prev_ts).total_seconds() > time_gap_hours * 3600:
            if current:
                clusters.append(current)
            current = [c]
        else:
            current.append(c)
        prev_ts = ts
    if current:
        clusters.append(current)

    # Further split large clusters by topic.
    final_clusters: list[list[CommitInfo]] = []
    for cluster in clusters:
        if len(cluster) <= 6:
            final_clusters.append(cluster)
            continue
        by_topic: dict[str, list[CommitInfo]] = {}
        for c in cluster:
            topic = _topic_of(c.message, [])
            by_topic.setdefault(topic, []).append(c)
        final_clusters.extend(by_topic.values())

    sprints: list[ArchitecturalSprint] = []
    for i, cluster in enumerate(final_clusters, 1):
        cluster = sorted(cluster, key=lambda c: _parse_ts(c.timestamp))
        first, last = cluster[0], cluster[-1]
        files = [f for c in cluster for f in _files_heuristic(c.message)]
        topic = _topic_of(" ".join(c.message for c in cluster), files)
        added = sorted({f for c in cluster for f in _extract_paths(c.message) if "add" in c.message.lower()})
        sprints.append(ArchitecturalSprint(
            id=f"sprint-{i:02d}",
            name=topic,
            time_range=(first.timestamp, last.timestamp),
            objective=_objective(topic),
            architectural_changes=_changes(cluster),
            components_added=added[:20],
            behavior_changes=_changes(cluster)[:5],
            evidence=[Evidence(file="git", reason=f"{len(cluster)} commit(s)")],
            commits=cluster,
            confidence=Confidence(score=0.6, rationale="time+topic clustering"),
        ))
        # Record facts/inferences about evolution.
        timeline.facts.append(f"Sprint {i} ({topic}): {len(cluster)} commit(s)")
        timeline.inferences.append(f"{topic} was a distinct architectural evolution phase")

    timeline.sprints = sprints
    return timeline


def _files_heuristic(message: str) -> list[str]:
    return _extract_paths(message)


def _extract_paths(message: str) -> list[str]:
    return re.findall(r"[\w./\-]+\.\w{1,5}", message)


def _objective(topic: str) -> str:
    return {
        "API layer": "Introduce or evolve the HTTP/API surface",
        "Database / persistence": "Introduce or evolve persistence and data modeling",
        "Authentication": "Add or change authentication and authorization",
        "Frontend / UI": "Build or change the user interface",
        "Background processing": "Add or change asynchronous/background work",
        "Deployment / infrastructure": "Add or change deployment and infrastructure",
        "Testing": "Add or expand tests",
        "Documentation": "Improve documentation",
        "Configuration": "Change configuration handling",
        "Refactoring": "Restructure existing code without behavior change",
        "General development": "General feature development",
    }.get(topic, "General development")


def _changes(cluster: list[CommitInfo]) -> list[str]:
    c: Counter[str] = Counter()
    for commit in cluster:
        topic = _topic_of(commit.message, [])
        c[topic] += 1
    return [f"{topic} ({n} commit(s))" for topic, n in c.most_common(5)]
