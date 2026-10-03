"""Dependency manifest analysis: requirements.txt, package.json, go.mod, etc."""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.analyzers.base import BaseAnalyzer
from app.analyzers.source_graph import FileEntry, SourceGraph
from app.domain.common import Confidence
from app.domain.technology import DependencyInfo, TechnologyKind

_PURPOSE_BY_NAME: dict[str, tuple[str, str, str]] = {
    "fastapi": ("HTTP API framework", "api", "critical"),
    "flask": ("HTTP API framework", "api", "critical"),
    "django": ("Web framework", "application", "critical"),
    "uvicorn": ("ASGI server", "infrastructure", "major"),
    "gunicorn": ("WSGI server", "infrastructure", "major"),
    "sqlalchemy": ("ORM / database abstraction", "persistence", "critical"),
    "alembic": ("Database migrations", "persistence", "major"),
    "psycopg2": ("PostgreSQL driver", "persistence", "major"),
    "psycopg": ("PostgreSQL driver", "persistence", "major"),
    "pymysql": ("MySQL driver", "persistence", "major"),
    "pymongo": ("MongoDB driver", "persistence", "major"),
    "redis": ("Cache / broker client", "infrastructure", "major"),
    "celery": ("Distributed task queue", "background", "major"),
    "pydantic": ("Data validation / schemas", "domain", "major"),
    "pydantic-settings": ("Configuration loading", "configuration", "minor"),
    "httpx": ("HTTP client", "integration", "minor"),
    "requests": ("HTTP client", "integration", "minor"),
    "aiohttp": ("Async HTTP client/server", "integration", "major"),
    "click": ("CLI framework", "cli", "minor"),
    "typer": ("CLI framework", "cli", "minor"),
    "pytest": ("Testing framework", "testing", "major"),
    "jinja2": ("Templating", "presentation", "minor"),
    "react": ("Frontend UI framework", "presentation", "critical"),
    "vue": ("Frontend UI framework", "presentation", "critical"),
    "express": ("HTTP server framework", "api", "critical"),
    "next": ("React meta-framework", "presentation", "critical"),
    "typescript": ("Typed JavaScript", "language-tooling", "major"),
    "vite": ("Frontend build tool", "tooling", "major"),
    "tailwindcss": ("CSS utility framework", "presentation", "minor"),
    "jest": ("JS testing framework", "testing", "major"),
    "vitest": ("JS testing framework", "testing", "major"),
    "axios": ("HTTP client", "integration", "minor"),
    "lodash": ("Utility library", "utility", "minor"),
    "numpy": ("Numerical computing", "domain", "major"),
    "pandas": ("Data analysis", "domain", "major"),
    "scikit-learn": ("Machine learning", "domain", "major"),
    "tensorflow": ("Machine learning", "domain", "major"),
    "torch": ("Machine learning", "domain", "major"),
    "pillow": ("Image processing", "domain", "minor"),
    "gunicorn[gevent]": ("WSGI server", "infrastructure", "major"),
    # Geospatial, 3D Graphics, & Situational Awareness
    "cesium": ("3D Geospatial & WebGL Globe Engine", "presentation", "critical"),
    "satellite.js": ("SGP4/SDP4 Satellite Orbit Propagation", "domain", "major"),
    "hls.js": ("HTTP Live Streaming (HLS) Video Player", "presentation", "major"),
    "ws": ("WebSocket Client & Server Transport", "integration", "major"),
    "@mapbox/vector-tile": ("Mapbox Vector Tile (MVT) Decoder", "domain", "major"),
    "@meri-imperiumi/eccodes-wasm": ("Wasm GRIB / Atmospheric Weather Decoder", "domain", "major"),
    "pbf": ("Protocol Buffers Binary Decoder", "utility", "minor"),
    "mgrs": ("Military Grid Reference System Coordinates", "domain", "minor"),
    "egm96-universal": ("Earth Gravitational Model Geoid Undulation", "domain", "minor"),
    "@jtarrio/signals": ("Reactive Signals State Management", "application", "major"),
    "@jtarrio/webrtlsdr": ("WebUSB RTL-SDR Radio Receiver", "integration", "major"),
    "vite-plugin-cesium": ("Vite Plugin for CesiumJS Assets", "tooling", "minor"),
    "prettier": ("Code Formatter", "tooling", "minor"),
    "puppeteer": ("Headless Browser Automation / Testing", "testing", "minor"),
    "sharp": ("High-performance Image Processing", "utility", "minor"),
    "three": ("3D WebGL Library", "presentation", "critical"),
    "leaflet": ("2D Interactive Mapping", "presentation", "critical"),
    "openlayers": ("High-performance Mapping", "presentation", "critical"),
    "turf": ("Geospatial Analysis Engine", "domain", "major"),
    "@turf/turf": ("Geospatial Analysis Engine", "domain", "major"),
    "proj4": ("Coordinate Projection Transformations", "domain", "major"),
    "geolib": ("Geographic Distance & Calculations", "domain", "minor"),
    "socket.io": ("Real-time Bidirectional WebSocket Engine", "integration", "major"),
    "socket.io-client": ("WebSocket Client", "integration", "major"),
    "eslint": ("JavaScript / TypeScript Linter", "tooling", "minor"),
    "nodemon": ("Development Auto-reloading Tool", "tooling", "minor"),
    "dotenv": ("Environment Configuration Loader", "configuration", "minor"),
}


class DependencyAnalyzer(BaseAnalyzer):
    """Parses dependency manifests into DependencyInfo objects."""

    name = "dependencies"

    _MANIFESTS = {
        "requirements.txt": "python",
        "pyproject.toml": "python",
        "setup.py": "python",
        "Pipfile": "python",
        "package.json": "javascript",
        "go.mod": "go",
        "Cargo.toml": "rust",
        "pom.xml": "java",
        "build.gradle": "java",
        "composer.json": "php",
        "Gemfile": "ruby",
        "pubspec.yaml": "dart",
    }

    def applicable(self, files: list[FileEntry]) -> bool:
        return any(f.path.split("/")[-1] in self._MANIFESTS for f in files)

    def analyze(self, root: str, files: list[FileEntry], graph: SourceGraph, ctx: dict) -> list[DependencyInfo]:
        deps: list[DependencyInfo] = []
        root_path = Path(root)
        for f in files:
            name = f.path.split("/")[-1]
            if name not in self._MANIFESTS or f.is_binary:
                continue
            try:
                text = (root_path / f.path).read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if name == "requirements.txt":
                deps.extend(self._parse_requirements(text, f.path))
            elif name == "package.json":
                deps.extend(self._parse_package_json(text, f.path))
            elif name == "go.mod":
                deps.extend(self._parse_go_mod(text, f.path))
            elif name == "pyproject.toml":
                deps.extend(self._parse_pyproject(text, f.path))
            elif name == "Cargo.toml":
                deps.extend(self._parse_cargo(text, f.path))
        # De-duplicate by name.
        seen: dict[str, DependencyInfo] = {}
        for d in deps:
            seen.setdefault(d.name, d)
        return list(seen.values())

    def _classify(self, name: str, section: str = "dependencies") -> tuple[str, str, str]:
        base = name.lower().split("[")[0].split(">")[0].split("=")[0].split("<")[0].strip()
        if base in _PURPOSE_BY_NAME:
            return _PURPOSE_BY_NAME[base]

        unscoped = base.split("/")[-1]
        if unscoped in _PURPOSE_BY_NAME:
            return _PURPOSE_BY_NAME[unscoped]

        # Pattern-based heuristics
        if any(t in unscoped for t in ("test", "mock", "jest", "vitest", "cypress", "playwright", "puppeteer", "coverage")):
            return ("Testing & Quality Assurance", "testing", "minor" if section == "devDependencies" else "major")
        if any(t in unscoped for t in ("lint", "prettier", "eslint", "format", "husky", "commitlint")):
            return ("Code Formatting & Quality", "tooling", "minor")
        if any(t in unscoped for t in ("build", "bundle", "webpack", "vite", "rollup", "esbuild", "babel", "swc", "plugin-")):
            return ("Build & Bundling Tool", "tooling", "minor" if "plugin" in unscoped else "major")
        if any(t in unscoped for t in ("cesium", "three", "babylon", "webgl", "globe", "canvas")):
            return ("3D Graphics & Visualization", "presentation", "critical")
        if any(t in unscoped for t in ("tile", "geo", "map", "gis", "proj", "coord", "satellite", "grib", "orbit", "elevation", "heights")):
            return ("Geospatial & Telemetry Processing", "domain", "major")
        if any(t in unscoped for t in ("stream", "socket", "ws", "hls", "webrtc", "mqtt")):
            return ("Streaming & Real-time Transport", "integration", "major")
        if any(t in unscoped for t in ("signal", "redux", "zustand", "mobx", "store", "state")):
            return ("State Management", "application", "major")
        if any(t in unscoped for t in ("sql", "db", "mongo", "redis", "postgres", "prisma", "typeorm", "cache")):
            return ("Database & Cache Client", "persistence", "critical")
        if any(t in unscoped for t in ("auth", "jwt", "crypto", "bcrypt", "oauth")):
            return ("Authentication & Security", "security", "critical")

        if section in ("devDependencies", "dev_dependencies", "test"):
            return ("Third-party dependency", "tooling", "minor")
        return ("Third-party dependency", "utility", "minor")

    def _parse_requirements(self, text: str, path: str) -> list[DependencyInfo]:
        out: list[DependencyInfo] = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            m = re.match(r"^([A-Za-z0-9_.\-]+)([<>=!~].*)?$", line)
            if not m:
                continue
            name = m.group(1).lower()
            version = (m.group(2) or "").strip() or None
            purpose, layer, crit = self._classify(name, section="dependencies")
            out.append(DependencyInfo(
                name=name, version=version, kind=TechnologyKind.LIBRARY,
                used_by=[path], purpose=purpose, architectural_layer=layer,
                criticality=crit, confidence=Confidence(score=0.9, rationale="manifest declaration"),
            ))
        return out

    def _parse_package_json(self, text: str, path: str) -> list[DependencyInfo]:
        out: list[DependencyInfo] = []
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return out
        for section in ("dependencies", "devDependencies"):
            for name, version in (data.get(section) or {}).items():
                purpose, layer, crit = self._classify(name, section=section)
                out.append(DependencyInfo(
                    name=name, version=str(version), kind=TechnologyKind.LIBRARY,
                    used_by=[path], purpose=purpose, architectural_layer=layer,
                    criticality=crit, confidence=Confidence(score=0.9, rationale=section),
                ))
        return out

    def _parse_go_mod(self, text: str, path: str) -> list[DependencyInfo]:
        out: list[DependencyInfo] = []
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("require ("):
                continue
            m = re.match(r"^\s*([\w./\-]+)\s+(v[\w.+\-]+)", line)
            if m:
                name = m.group(1).split("/")[-1]
                purpose, layer, crit = self._classify(name)
                out.append(DependencyInfo(
                    name=name, version=m.group(2), kind=TechnologyKind.LIBRARY,
                    used_by=[path], purpose=purpose, architectural_layer=layer,
                    criticality=crit, confidence=Confidence(score=0.9, rationale="go.mod"),
                ))
        return out

    def _parse_pyproject(self, text: str, path: str) -> list[DependencyInfo]:
        out: list[DependencyInfo] = []
        for m in re.finditer(r'^([A-Za-z0-9_.\-]+)\s*(?:[<>=!~][^"\']*)?', text, re.M):
            line = m.group(0).strip()
            if not line or line.startswith("[") or line.startswith("#"):
                continue
            name = re.match(r"^([A-Za-z0-9_.\-]+)", line)
            if name:
                n = name.group(1).lower()
                purpose, layer, crit = self._classify(n)
                out.append(DependencyInfo(
                    name=n, kind=TechnologyKind.LIBRARY, used_by=[path],
                    purpose=purpose, architectural_layer=layer, criticality=crit,
                    confidence=Confidence(score=0.7, rationale="pyproject dependency"),
                ))
        return out

    def _parse_cargo(self, text: str, path: str) -> list[DependencyInfo]:
        out: list[DependencyInfo] = []
        for m in re.finditer(r'^([A-Za-z0-9_\-]+)\s*=\s*"[^"]*"', text, re.M):
            name = m.group(1)
            purpose, layer, crit = self._classify(name)
            out.append(DependencyInfo(
                name=name, kind=TechnologyKind.LIBRARY, used_by=[path],
                purpose=purpose, architectural_layer=layer, criticality=crit,
                confidence=Confidence(score=0.8, rationale="Cargo.toml"),
            ))
        return out
