"""Documentation analysis: parse docs and cross-check claims against the source."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.analyzers.base import BaseAnalyzer
from app.analyzers.source_graph import FileEntry, SourceGraph
from app.domain.technology import TechnologyStack

_TECH_CLAIM_RE = re.compile(
    r"\b(FastAPI|Flask|Django|React|Next\.js|Vue|Angular|Express|Spring|"
    r"PostgreSQL|MySQL|SQLite|MongoDB|Redis|Elasticsearch|Docker|Kubernetes|"
    r"TypeScript|JavaScript|Python|Go|Rust|Java|GraphQL|gRPC|Celery|Kafka|RabbitMQ)\b",
    re.I,
)


class DocumentationAnalyzer(BaseAnalyzer):
    name = "docs"

    def applicable(self, files: list[FileEntry]) -> bool:
        return any(f.category.value == "doc" for f in files)

    def analyze(self, root: str, files: list[FileEntry], graph: SourceGraph, ctx: dict) -> dict[str, Any]:
        stack: TechnologyStack = ctx.get("technologies") or TechnologyStack()
        result: dict[str, Any] = {
            "files": [],
            "claims": [],
            "headings": [],
            "discrepancies": [],
        }
        root_path = Path(root)
        known_tech = set()
        if stack:
            known_tech = {
                t.name.lower()
                for t in stack.languages + stack.frameworks + stack.databases + stack.infrastructure
            }
        for f in files:
            if f.category.value != "doc" or f.is_binary:
                continue
            try:
                text = (root_path / f.path).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            result["files"].append(f.path)
            result["headings"].extend(re.findall(r"^#{1,3}\s+(.+)$", text, re.M))
            for m in _TECH_CLAIM_RE.finditer(text):
                claim = m.group(1)
                result["claims"].append(claim)
                if claim.lower() not in known_tech:
                    result["discrepancies"].append({
                        "doc": f.path,
                        "claim": claim,
                        "status": "UNKNOWN" if known_tech else "CONFLICT",
                    })
        # De-duplicate discrepancies.
        seen = set()
        deduped = []
        for d in result["discrepancies"]:
            key = (d["claim"], d["status"])
            if key not in seen:
                seen.add(key)
                deduped.append(d)
        result["discrepancies"] = deduped
        return result
