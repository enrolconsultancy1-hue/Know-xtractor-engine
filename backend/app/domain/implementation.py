"""Implementation specification model."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ImplementationSpec(BaseModel):
    """The complete, implementation-ready specification."""

    project_objective: str = ""
    functional_requirements: list[str] = Field(default_factory=list)
    non_functional_requirements: list[str] = Field(default_factory=list)
    architecture: list[str] = Field(default_factory=list)
    technology_stack: dict[str, str] = Field(default_factory=dict)
    domain_model: list[str] = Field(default_factory=list)
    api_specification: list[str] = Field(default_factory=list)
    workflows: list[str] = Field(default_factory=list)
    database: list[str] = Field(default_factory=list)
    configuration: list[str] = Field(default_factory=list)
    security: list[str] = Field(default_factory=list)
    testing: list[str] = Field(default_factory=list)
    deployment: list[str] = Field(default_factory=list)
    implementation_order: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)

    def to_prompt(self, project_name: str) -> str:
        """Render the spec as a single implementation prompt for a coding agent."""

        def block(title: str, items: list[str]) -> str:
            if not items:
                return f"## {title}\n\n_(not specified)_\n"
            return f"## {title}\n\n" + "\n".join(f"- {i}" for i in items) + "\n"

        sections: list[str] = [f"IMPLEMENT THIS ARCHITECTURE\n\nProject: {project_name}"]
        sections.append(f"Objective: {self.project_objective or '(see functional requirements)'}")
        sections.append(block("Functional Requirements", self.functional_requirements))
        sections.append(block("Non-Functional Requirements", self.non_functional_requirements))
        sections.append(block("Architecture", self.architecture))
        if self.technology_stack:
            sections.append(
                "## Technology Stack\n\n"
                + "\n".join(f"- {k}: {v}" for k, v in self.technology_stack.items())
                + "\n"
            )
        sections.append(block("Domain Model", self.domain_model))
        sections.append(block("APIs", self.api_specification))
        sections.append(block("Workflows", self.workflows))
        sections.append(block("Database", self.database))
        sections.append(block("Configuration", self.configuration))
        sections.append(block("Security", self.security))
        sections.append(block("Testing Requirements", self.testing))
        sections.append(block("Deployment", self.deployment))
        sections.append(block("Implementation Order", self.implementation_order))
        sections.append(block("Acceptance Criteria", self.acceptance_criteria))
        return "\n\n".join(sections)
