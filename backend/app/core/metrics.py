"""Minimal dependency-free Prometheus-style metrics for KNOX.

Implements only the small subset KNOX needs (Counter / Gauge / Histogram) with
a text-format exporter for the ``/metrics`` endpoint. No external client library
is pinned, keeping the Python 3.14 dependency surface minimal.
"""

from __future__ import annotations

import threading
from collections.abc import Iterable, Iterator

_LOCK = threading.Lock()
_REGISTRY: list[_Metric] = []

DEFAULT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0)


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _labels_str(labels: dict[str, str]) -> str:
    if not labels:
        return ""
    parts = [f'{k}="{_escape_label(v)}"' for k, v in sorted(labels.items())]
    return "{" + ",".join(parts) + "}"


class _Metric:
    def __init__(self, name: str, help_: str, type_: str) -> None:
        self.name = name
        self.help = help_
        self.type = type_
        self._lock = threading.Lock()
        with _LOCK:
            _REGISTRY.append(self)

    def _lines(self) -> Iterator[str]:
        raise NotImplementedError


class Counter(_Metric):
    def __init__(self, name: str, help_: str, labelnames: Iterable[str] = ()) -> None:
        super().__init__(name, help_, "counter")
        self.labelnames = tuple(labelnames)
        self._values: dict[tuple[str, ...], float] = {}

    def _key(self, labels: dict[str, str] | None) -> tuple[str, ...]:
        labels = labels or {}
        return tuple(labels.get(n, "") for n in self.labelnames)

    def inc(self, amount: float = 1.0, labels: dict[str, str] | None = None) -> None:
        key = self._key(labels)
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + amount

    def _lines(self) -> Iterator[str]:
        with self._lock:
            items = list(self._values.items())
        for key, value in items:
            labels = dict(zip(self.labelnames, key, strict=True))
            yield f"{self.name}{_labels_str(labels)} {value}"


class Gauge(_Metric):
    def __init__(self, name: str, help_: str, labelnames: Iterable[str] = ()) -> None:
        super().__init__(name, help_, "gauge")
        self.labelnames = tuple(labelnames)
        self._values: dict[tuple[str, ...], float] = {}

    def _key(self, labels: dict[str, str] | None) -> tuple[str, ...]:
        labels = labels or {}
        return tuple(labels.get(n, "") for n in self.labelnames)

    def set(self, value: float, labels: dict[str, str] | None = None) -> None:
        key = self._key(labels)
        with self._lock:
            self._values[key] = value

    def inc(self, amount: float = 1.0, labels: dict[str, str] | None = None) -> None:
        key = self._key(labels)
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + amount

    def dec(self, amount: float = 1.0, labels: dict[str, str] | None = None) -> None:
        self.inc(-amount, labels)

    def _lines(self) -> Iterator[str]:
        with self._lock:
            items = list(self._values.items())
        for key, value in items:
            labels = dict(zip(self.labelnames, key, strict=True))
            yield f"{self.name}{_labels_str(labels)} {value}"


class Histogram(_Metric):
    def __init__(self, name: str, help_: str, labelnames: Iterable[str] = (),
                 buckets: Iterable[float] = DEFAULT_BUCKETS) -> None:
        super().__init__(name, help_, "histogram")
        self.labelnames = tuple(labelnames)
        self.buckets = tuple(buckets)
        self._counts: dict[tuple[str, ...], float] = {}
        self._sums: dict[tuple[str, ...], float] = {}
        self._bucket_counts: dict[tuple[str, ...], dict[float, float]] = {}

    def _key(self, labels: dict[str, str] | None) -> tuple[str, ...]:
        labels = labels or {}
        return tuple(labels.get(n, "") for n in self.labelnames)

    def observe(self, value: float, labels: dict[str, str] | None = None) -> None:
        key = self._key(labels)
        with self._lock:
            self._counts[key] = self._counts.get(key, 0.0) + 1.0
            self._sums[key] = self._sums.get(key, 0.0) + value
            bucket = self._bucket_counts.setdefault(key, {})
            for upper in self.buckets:
                if value <= upper:
                    bucket[upper] = bucket.get(upper, 0.0) + 1.0

    def _lines(self) -> Iterator[str]:
        with self._lock:
            keys = sorted(self._counts.keys())
            for key in keys:
                labels = dict(zip(self.labelnames, key, strict=True))
                bucket = self._bucket_counts.get(key, {})
                cumulative = 0.0
                for upper in self.buckets:
                    cumulative += bucket.get(upper, 0.0)
                    lab = {"le": repr(upper), **labels}
                    yield f"{self.name}_bucket{_labels_str(lab)} {cumulative}"
                lab_inf = {"le": "+Inf", **labels}
                yield f"{self.name}_bucket{_labels_str(lab_inf)} {self._counts.get(key, 0.0)}"
                yield f"{self.name}_sum{_labels_str(labels)} {self._sums.get(key, 0.0)}"
                yield f"{self.name}_count{_labels_str(labels)} {self._counts.get(key, 0.0)}"


def generate_latest() -> str:
    with _LOCK:
        metrics = list(_REGISTRY)
    lines: list[str] = []
    for m in metrics:
        lines.append(f"# HELP {m.name} {m.help}")
        lines.append(f"# TYPE {m.name} {m.type}")
        lines.extend(m._lines())
    if lines:
        return "\n".join(lines) + "\n"
    return ""


# Shared metric objects (singletons).
http_requests_total = Counter(
    "http_requests_total", "Total HTTP requests processed.", ["method", "path", "status"]
)
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds", "HTTP request latency in seconds.", ["method", "path"]
)
knox_analysis_runs_total = Counter(
    "knox_analysis_runs_total", "Analysis runs by terminal status.", ["status"]
)
knox_analysis_duration_seconds = Histogram(
    "knox_analysis_duration_seconds", "Analysis pipeline duration in seconds."
)
knox_queue_depth = Gauge("knox_queue_depth", "Analysis jobs currently queued.")
