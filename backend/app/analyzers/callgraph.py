"""Call-graph and data-flow analysis.

The Python/tree-sitter analyzers record *call sites* on each symbol, but those
are unqualified strings and only the immediate level is used. This module
resolves those calls into a graph and classifies each target's *data flow*
(persistence / external service / cache / queue), then supports bounded,
cycle-safe recursive tracing — turning "list of calls" into "request lifecycle".

Everything here is a deterministic inference over static structure; it never
executes code and never reads values.
"""

from __future__ import annotations

from collections import deque
from enum import Enum

from app.analyzers.source_graph import SourceGraph, Symbol


class CallKind(str, Enum):
    INTERNAL = "internal"
    PERSISTENCE = "persistence"
    EXTERNAL = "external"
    CACHE = "cache"
    QUEUE = "queue"
    UNKNOWN = "unknown"


# Substring markers used to classify call targets. Kept conservative: they only
# trigger on ORM/network/broker-specific tokens, not on generic verbs. Call
# names are paren-free (e.g. ``session.query``, ``requests.get``).
_PERSISTENCE_MARKERS = (
    "session.query", "session.add", "session.commit", "session.execute",
    "session.flush", "session.merge", "session.delete", "session.scalar",
    "session.scalars", ".objects.", ".query", ".execute", ".executemany",
    ".commit", ".rollback", "bulk_create", "get_or_create", "select_related",
    "prefetch_related", "cursor.", ".raw",
)
_EXTERNAL_MARKERS = (
    "requests.", "httpx.", "urllib.", "urlopen", "aiohttp.", "axios",
    "socket.", "grpc.",
)
_CACHE_MARKERS = (
    "redis", "memcached", ".cache", "get_cache", "set_cache",
)
_QUEUE_MARKERS = (
    "celery", "kafka", "rabbitmq", "enqueue", "publish", "send_task",
    "dramatiq", "apply_async", ".delay", "rq.",
)


def classify_call(name: str) -> CallKind:
    """Classify a call target by its data-flow role."""
    n = name.lower()
    if any(m in n for m in _PERSISTENCE_MARKERS):
        return CallKind.PERSISTENCE
    if n == "fetch" or any(m in n for m in _EXTERNAL_MARKERS):
        return CallKind.EXTERNAL
    if any(m in n for m in _QUEUE_MARKERS):
        return CallKind.QUEUE
    if any(m in n for m in _CACHE_MARKERS):
        return CallKind.CACHE
    return CallKind.UNKNOWN


class CallGraph:
    """Resolved call graph over the source graph's symbols."""

    def __init__(self, graph: SourceGraph) -> None:
        self.graph = graph
        self._by_id: dict[str, Symbol] = {}
        self._by_short: dict[str, list[Symbol]] = {}
        for module in graph.modules.values():
            for sym in module.symbols:
                self._by_id[self.symbol_id(sym)] = sym
                self._by_short.setdefault(sym.name, []).append(sym)
        self._edges: dict[str, list[tuple[str, CallKind, str | None]]] = {}
        self._build()

    @staticmethod
    def symbol_id(sym: Symbol) -> str:
        return f"{sym.path}:{sym.name}"

    def _build(self) -> None:
        for sym in self.graph.all_symbols():
            sid = self.symbol_id(sym)
            edges: list[tuple[str, CallKind, str | None]] = []
            for call in sym.calls:
                kind = classify_call(call)
                target: str | None = None
                if kind is CallKind.UNKNOWN:
                    resolved = self._resolve(call, sym.path)
                    if resolved is not None:
                        target = resolved
                        kind = CallKind.INTERNAL
                edges.append((call, kind, target))
            self._edges[sid] = edges

    def _resolve(self, name: str, path: str) -> str | None:
        """Resolve a call name to a symbol id, or None if ambiguous/unresolved."""
        short = name.split(".")[-1]
        # Prefer a same-file match.
        same_file = [s for s in self._by_short.get(short, []) if s.path == path]
        if len(same_file) == 1:
            return self.symbol_id(same_file[0])
        global_matches = self._by_short.get(short, [])
        if len(global_matches) == 1:
            return self.symbol_id(global_matches[0])
        return None

    def callees_of(self, symbol_id: str) -> list[tuple[str, CallKind]]:
        return [(label, kind) for label, kind, _ in self._edges.get(symbol_id, [])]

    def trace(self, symbol_id: str, max_depth: int = 6, max_nodes: int = 40) -> list[tuple[str, CallKind, int]]:
        """BFS over resolved internal edges.

        Returns ``(label, kind, depth)`` in visit order (callees of the given
        symbol; the symbol itself is the implicit root). Cycle-safe and bounded.
        """
        order: list[tuple[str, CallKind, int]] = []
        seen: set[str] = set()
        queue: deque[tuple[str, int]] = deque([(symbol_id, 0)])
        while queue and len(order) < max_nodes:
            sid, depth = queue.popleft()
            if sid in seen or depth > max_depth:
                continue
            seen.add(sid)
            for label, kind, target in self._edges.get(sid, []):
                if len(order) >= max_nodes:
                    break
                order.append((label, kind, depth))
                if kind is CallKind.INTERNAL and target is not None:
                    queue.append((target, depth + 1))
        return order

    def reachable_kinds(self, symbol_id: str, max_depth: int = 6) -> set[CallKind]:
        """Data-flow roles reachable from a symbol (persistence/external/queue/
        cache). Internal and unknown hops are not reported."""
        meaningful = {
            CallKind.PERSISTENCE, CallKind.EXTERNAL, CallKind.QUEUE, CallKind.CACHE,
        }
        return {kind for _, kind, _ in self.trace(symbol_id, max_depth=max_depth) if kind in meaningful}
