"""Knowledge graph builder: a queryable entity/relationship graph."""

from __future__ import annotations

from typing import Any

from app.domain.component import Component
from app.domain.data_model import DataModel
from app.domain.knowledge import KnowledgePackage
from app.domain.sprint import ArchitecturalSprint
from app.domain.technology import DependencyInfo
from app.domain.workflow import Workflow


class KnowledgeGraph:
    """Builds a machine-readable graph from the knowledge package."""

    def __init__(self, pkg: KnowledgePackage) -> None:
        self.pkg = pkg

    def build(self) -> dict[str, Any]:
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []

        # Project node.
        nodes.append({"id": "project", "type": "Project", "label": self.pkg.metadata.get("repository", "project")})

        # Technology nodes.
        for tech in (self.pkg.technologies.languages + self.pkg.technologies.frameworks
                     + self.pkg.technologies.databases + self.pkg.technologies.infrastructure):
            nid = f"tech:{tech.name}"
            nodes.append({"id": nid, "type": "Technology", "label": tech.name})
            edges.append({"source": "project", "target": nid, "relation": "USES"})

        # Dependency nodes.
        for dep in self.pkg.technologies.dependencies:
            nid = f"dep:{dep.name}"
            nodes.append({"id": nid, "type": "Dependency", "label": dep.name})
            edges.append({"source": "project", "target": nid, "relation": "DEPENDS_ON"})

        # Component nodes + relations.
        for comp in self.pkg.components:
            nid = comp.id
            nodes.append({"id": nid, "type": "Component", "label": comp.name})
            edges.append({"source": "project", "target": nid, "relation": "CONTAINS"})
            for dep_name in comp.dependencies:
                edges.append({"source": nid, "target": dep_name, "relation": "DEPENDS_ON"})

        # Data entities.
        for ent in self.pkg.data_model.entities:
            nid = f"entity:{ent.name}"
            nodes.append({"id": nid, "type": "Model", "label": ent.name})
            edges.append({"source": "project", "target": nid, "relation": "CONTAINS"})
        for rel in self.pkg.data_model.relationships:
            edges.append({
                "source": f"entity:{rel.source}",
                "target": f"entity:{rel.target}",
                "relation": "RELATES_TO",
            })

        # Workflows.
        for wf in self.pkg.workflows:
            nid = wf.id
            nodes.append({"id": nid, "type": "Workflow", "label": wf.name})
            edges.append({"source": "project", "target": nid, "relation": "CONTAINS"})
            for s, t in wf.edges():
                edges.append({"source": s, "target": t, "relation": "CALLS"})

        # Sprints.
        for sp in self.pkg.architectural_sprints.sprints:
            nid = sp.id
            nodes.append({"id": nid, "type": "Sprint", "label": sp.name})
            edges.append({"source": "project", "target": nid, "relation": "EVOLVED_IN"})

        # De-duplicate nodes/edges.
        return {
            "nodes": self._dedupe(nodes, "id"),
            "edges": self._dedupe(edges, "source"),
            "counts": {"nodes": len(nodes), "edges": len(edges)},
        }

    @staticmethod
    def _dedupe(items: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        for it in items:
            k = it.get(key)
            if k is not None and k not in seen:
                seen.add(k)
                out.append(it)
        return out


def build_knowledge_graph(pkg: KnowledgePackage) -> dict[str, Any]:
    return KnowledgeGraph(pkg).build()


# Re-export for convenience.
__all__ = ["KnowledgeGraph", "build_knowledge_graph", "Component", "DependencyInfo",
           "Workflow", "ArchitecturalSprint", "DataModel"]
