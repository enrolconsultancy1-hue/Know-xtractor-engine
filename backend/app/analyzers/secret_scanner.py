"""Hardcoded-secret detection in source code.

KNOX treats every repository as untrusted and never persists secret *values*.
This scanner records only the location (file + line), the key/category, and a
weighted confidence. No literal value is ever stored or logged.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.analyzers.base import BaseAnalyzer
from app.analyzers.source_graph import FileCategory, FileEntry, SourceGraph
from app.core.security import classify_secret_key

# High-confidence literal patterns (known secret formats).
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("github_token", re.compile(r"\bgh[pousr]_[0-9A-Za-z]{20,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b")),
    ("stripe_key", re.compile(r"\bsk_(?:live|test)_[0-9A-Za-z]{10,}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")),
    ("connection_string", re.compile(
        r"(?i)\b(?:postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?|redis|amqp)://[^:\s\"']+:[^\s\"'@/]+@"
    )),
]

# Secret-looking names (excludes bare `token`/`key`, which are too noisy in
# lexers/parsers). Matched anywhere on the line when followed by a literal.
_SECRET_NAME = (
    r"(?i:api[_-]?key|apikey|api[_-]?token|access[_-]?token|auth[_-]?token|refresh[_-]?token"
    r"|jwt[_-]?secret|client[_-]?secret|private[_-]?key|password|passwd|pwd|secret"
    r"|db[_-]?password|database[_-]?password|aws[_-]?secret|stripe[_-]?key)"
)
_SECRET_ASSIGN_RE = re.compile(
    r"\b(" + _SECRET_NAME + r")\b\s*[:=]\s*" + r"(['\"][^'\"]{4,}['\"]|(?:0[xX])?[0-9a-fA-F]{32,})"
)

# Values that are placeholders, not real secrets.
_PLACEHOLDERS = {
    "", "password", "passwd", "pwd", "secret", "token", "api_key", "apikey",
    "changeme", "change_me", "your_password", "your_secret", "your_token",
    "xxx", "xxxx", "xxxxxx", "test", "testing", "example", "example_key",
    "none", "null", "true", "false", "sha256", "sha1", "md5", "bcrypt", "argon2",
}

# Key-name fragments that indicate a non-secret (algorithm/config policy).
_NON_SECRET_FRAGMENTS = ("hash", "salt", "algo", "algorithm", "scheme", "cipher", "policy")

_MAX_SCAN_BYTES = 512_000


def redact_known_secret_values(text: str) -> str:
    """Replace high-confidence secret literals (AWS keys, tokens, ...) with [REDACTED].

    Used by the opt-in logic-capture mode so captured function bodies can
    never re-materialize credential-looking literals.
    """
    for _category, pattern in _PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


def scan_source(text: str, rel: str) -> list[dict[str, Any]]:
    """Scan one source file's text for hardcoded secrets. Values are never returned."""
    findings: list[dict[str, Any]] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith(("#", "//", "*", "/*", ";")):
            continue
        # 1. Known secret formats -> high confidence.
        matched = False
        for category, pattern in _PATTERNS:
            if pattern.search(raw):
                findings.append({
                    "file": rel, "line": lineno, "key": category,
                    "category": category, "confidence": 0.9,
                })
                matched = True
                break
        if matched:
            continue
        # 2. Secret-named variable assigned a literal -> medium confidence.
        m = _SECRET_ASSIGN_RE.search(raw)
        if not m:
            continue
        name = m.group(1).lower()
        if any(frag in name for frag in _NON_SECRET_FRAGMENTS):
            continue
        value = m.group(2).strip().strip("'\"").lower()
        if value in _PLACEHOLDERS:
            continue
        findings.append({
            "file": rel, "line": lineno, "key": m.group(1),
            "category": classify_secret_key(name) or "credential", "confidence": 0.7,
        })
    return findings


class SecretScanner(BaseAnalyzer):
    """Scans source files for hardcoded secrets (locations only, never values)."""

    name = "secrets"

    def applicable(self, files: list[FileEntry]) -> bool:
        return any(f.category == FileCategory.SOURCE for f in files)

    def analyze(self, root: str, files: list[FileEntry], graph: SourceGraph, ctx: dict) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        root_path = Path(root)
        for f in files:
            if f.is_binary or f.category != FileCategory.SOURCE:
                continue
            try:
                text = (root_path / f.path).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if len(text) > _MAX_SCAN_BYTES:
                text = text[:_MAX_SCAN_BYTES]
            findings.extend(scan_source(text, f.path))
        return findings
