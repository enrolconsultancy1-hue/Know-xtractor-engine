"""Language & technology detection from the file inventory and manifests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.analyzers.base import BaseAnalyzer
from app.analyzers.source_graph import FileEntry, SourceGraph
from app.domain.common import Confidence, Evidence
from app.domain.technology import Technology, TechnologyKind, TechnologyStack

# Framework / database / infra detection heuristics.
_FRAMEWORKS: dict[str, list[str]] = {
    "FastAPI": ["fastapi", "from fastapi", "APIRouter"],
    "Flask": ["flask", "from flask"],
    "Django": ["django", "from django", "manage.py"],
    "React": [".jsx", ".tsx", "from 'react'", "from \"react\"", "react-dom"],
    "Next.js": ["next/", "next.config"],
    "Vue": [".vue", "from 'vue'"],
    "Angular": ["@angular"],
    "Express": ["express"],
    "Spring": ["org.springframework"],
    ".NET": [".csproj", "Microsoft.AspNetCore"],
    "Flutter": ["pubspec.yaml", "package:flutter"],
    "Celery": ["celery"],
    "SQLAlchemy": ["sqlalchemy", "declarative_base", "from sqlalchemy"],
    "Pydantic": ["pydantic", "BaseModel"],
    "Gin": ["github.com/gin-gonic"],
}

_DATABASES: dict[str, list[str]] = {
    "PostgreSQL": ["postgresql", "psycopg", "postgres"],
    "MySQL": ["mysql", "pymysql", "mariadb"],
    "SQLite": ["sqlite", "sqlite3"],
    "MongoDB": ["mongodb", "pymongo", "mongoose"],
    "Redis": ["redis", "redis-py"],
    "Elasticsearch": ["elasticsearch"],
}

_INFRA: dict[str, list[str]] = {
    "Docker": ["Dockerfile", "docker-compose"],
    "Kubernetes": [".k8s", "k8s", "helm", "kubectl", "deployment.yaml"],
    "GitHub Actions": [".github/workflows"],
    "Terraform": [".tf", "terraform"],
    "AWS": ["boto3", "aws-sdk", "amazonaws"],
    "Azure": ["azure", "azure-sdk"],
    "GCP": ["google.cloud", "gcloud"],
    "RabbitMQ": ["rabbitmq", "amqp", "pika"],
    "Kafka": ["kafka", "confluent_kafka"],
    "Nginx": ["nginx"],
    "Celery": ["celery", "redis broker"],
}


class LanguageDetector(BaseAnalyzer):
    """Detects languages, frameworks, databases, and infrastructure."""

    name = "languages"

    def applicable(self, files: list[FileEntry]) -> bool:
        return True

    def analyze(self, root: str, files: list[FileEntry], graph: SourceGraph, ctx: dict) -> TechnologyStack:
        stack = TechnologyStack()
        root_path = Path(root)

        # Languages from extensions.
        lang_counts: dict[str, int] = {}
        for f in files:
            if f.language:
                lang_counts[f.language] = lang_counts.get(f.language, 0) + 1
        for lang, count in sorted(lang_counts.items(), key=lambda kv: -kv[1]):
            stack.languages.append(Technology(
                name=self._lang_display(lang),
                kind=TechnologyKind.LANGUAGE,
                confidence=Confidence(score=0.95, rationale=f"{count} file(s) with .{lang} extension"),
                evidence=[Evidence(file=f"*.{lang}", reason="file extension")],
            ))

        # Grep cheaply across text for framework/db/infra markers.
        marker_text = self._collect_marker_text(files, root_path)

        for name, markers in _FRAMEWORKS.items():
            if self._any_marker(markers, files, marker_text):
                stack.frameworks.append(Technology(
                    name=name, kind=TechnologyKind.FRAMEWORK,
                    confidence=Confidence(score=0.85, rationale="marker detected"),
                    evidence=[Evidence(file=self._marker_file(markers, files), reason="marker present")],
                ))

        for name, markers in _DATABASES.items():
            if self._any_marker(markers, files, marker_text):
                stack.databases.append(Technology(
                    name=name, kind=TechnologyKind.DATABASE,
                    confidence=Confidence(score=0.8, rationale="database marker detected"),
                    evidence=[Evidence(file=self._marker_file(markers, files), reason="marker present")],
                ))

        for name, markers in _INFRA.items():
            if self._any_marker(markers, files, marker_text):
                stack.infrastructure.append(Technology(
                    name=name, kind=TechnologyKind.INFRASTRUCTURE,
                    confidence=Confidence(score=0.8, rationale="infra marker detected"),
                    evidence=[Evidence(file=self._marker_file(markers, files), reason="marker present")],
                ))

        return stack

    @staticmethod
    def _lang_display(lang: str) -> str:
        return {
            "python": "Python",
            "javascript": "JavaScript",
            "typescript": "TypeScript",
            "go": "Go",
            "rust": "Rust",
            "java": "Java",
            "csharp": "C#",
            "cpp": "C++",
            "c": "C",
            "dart": "Dart",
            "php": "PHP",
            "ruby": "Ruby",
            "kotlin": "Kotlin",
            "swift": "Swift",
            "scala": "Scala",
            "shell": "Shell",
            "vue": "Vue",
            "svelte": "Svelte",
            "css": "CSS",
            "scss": "SCSS",
            "html": "HTML",
            "sql": "SQL",
        }.get(lang, lang)

    def _collect_marker_text(self, files: list[FileEntry], root: Path) -> str:
        """Read up to N config/manifest files' text for marker matching."""
        chunks: list[str] = []
        manifests = {
            "requirements.txt", "package.json", "pyproject.toml", "setup.py",
            "go.mod", "Cargo.toml", "pom.xml", "build.gradle", "composer.json",
            "Gemfile", "pubspec.yaml", "Pipfile", "poetry.lock",
        }
        for f in files:
            if f.path.split("/")[-1] in manifests and not f.is_binary:
                try:
                    text = (root / f.path).read_text(encoding="utf-8", errors="ignore")
                    chunks.append(text[:50_000])
                except OSError:
                    continue
        return "\n".join(chunks)

    def _any_marker(self, markers: list[str], files: list[FileEntry], text: str) -> bool:
        for m in markers:
            if m.startswith(".") or "/" in m or "\\" in m or "." in m and m.endswith((".yaml", ".yml", ".csproj", ".tf")):
                # file/path marker
                if any(m in f.path or f.path.endswith(m) or f.path.split("/")[-1] == m for f in files):
                    return True
            if m.lower() in text.lower():
                return True
            # Also scan filenames for extension markers (.jsx etc).
            if m.startswith("."):
                if any(f.path.endswith(m) for f in files):
                    return True
        return False

    def _marker_file(self, markers: list[str], files: list[FileEntry]) -> str:
        for m in markers:
            if m.startswith(".") or "/" in m:
                for f in files:
                    if f.path.endswith(m) or m in f.path:
                        return f.path
        return "manifest"
