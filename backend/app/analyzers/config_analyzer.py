"""Configuration analysis: extract config keys without ever persisting secrets."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from app.analyzers.base import BaseAnalyzer
from app.analyzers.source_graph import FileEntry, SourceGraph
from app.core.security import classify_secret_key

_CONFIG_EXTS = {".env", ".yaml", ".yml", ".json", ".toml", ".ini", ".cfg", ".conf"}


class ConfigAnalyzer(BaseAnalyzer):
    name = "config"

    def applicable(self, files: list[FileEntry]) -> bool:
        return any(f.path.split("/")[-1].lower() in {"dockerfile", ".env", "docker-compose.yml", "docker-compose.yaml"}
                   or f.path.endswith(tuple(_CONFIG_EXTS)) for f in files)

    def analyze(self, root: str, files: list[FileEntry], graph: SourceGraph, ctx: dict) -> dict[str, Any]:
        result: dict[str, Any] = {
            "files": [],
            "keys": {},
            "secret_required": [],
            "secrets_found": [],
        }
        root_path = Path(root)
        for f in files:
            if f.is_binary:
                continue
            name = f.path.split("/")[-1].lower()
            if name == "dockerfile":
                self._parse_dockerfile(root_path / f.path, f.path, result)
            elif name in {".env", "docker-compose.yml", "docker-compose.yaml"} or f.path.endswith(tuple(_CONFIG_EXTS)):
                self._parse_config(root_path / f.path, f.path, name, result)
        return result

    def _parse_config(self, path: Path, rel: str, name: str, result: dict) -> None:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return
        result["files"].append(rel)
        if name == ".env":
            self._parse_env(text, result)
        elif name.endswith((".yaml", ".yml")):
            self._parse_yaml(text, rel, result)
        elif name.endswith(".json"):
            self._parse_json(text, rel, result)
        elif name.endswith(".toml"):
            self._parse_toml(text, rel, result)
        elif name.endswith((".ini", ".cfg", ".conf")):
            self._parse_ini(text, rel, result)

    def _parse_env(self, text: str, result: dict) -> None:
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if not key:
                continue
            category = classify_secret_key(key)
            if category:
                result["secret_required"].append(key)
                result["secrets_found"].append({"key": key, "category": category, "value": "<REDACTED>"})
            else:
                result["keys"][key] = "<set>" if value.strip() else "<empty>"

    def _parse_yaml(self, text: str, rel: str, result: dict) -> None:
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError:
            result["keys"][rel] = "<unparseable>"
            return
        if isinstance(data, dict):
            for k, v in data.items():
                self._record_key(result, str(k), v)

    def _parse_json(self, text: str, rel: str, result: dict) -> None:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            result["keys"][rel] = "<unparseable>"
            return
        if isinstance(data, dict):
            for k, v in data.items():
                self._record_key(result, str(k), v)

    def _parse_toml(self, text: str, rel: str, result: dict) -> None:
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("["):
                continue
            if "=" in line:
                key = line.split("=")[0].strip()
                result["keys"][key] = "<set>"

    def _parse_ini(self, text: str, rel: str, result: dict) -> None:
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith(("#", ";")):
                continue
            if line.startswith("["):
                continue
            if "=" in line:
                key = line.split("=")[0].strip()
                category = classify_secret_key(key)
                if category:
                    result["secret_required"].append(key)
                else:
                    result["keys"][key] = "<set>"

    def _record_key(self, result: dict, key: str, value: Any) -> None:
        category = classify_secret_key(key)
        if category:
            result["secret_required"].append(key)
        elif isinstance(value, dict):
            result["keys"][key] = {str(k): "<value>" for k in value}
        elif isinstance(value, list):
            result["keys"][key] = "<list>"
        else:
            result["keys"][key] = "<set>" if value is not None else None

    def _parse_dockerfile(self, path: Path, rel: str, result: dict) -> None:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return
        result["files"].append(rel)
        images = re.findall(r"^FROM\s+(\S+)", text, re.M)
        if images:
            result["keys"]["_docker_base_images"] = images
        ports = re.findall(r"^EXPOSE\s+([\d\s]+)", text, re.M)
        if ports:
            result["keys"]["_docker_expose"] = [p.strip() for p in ports]
