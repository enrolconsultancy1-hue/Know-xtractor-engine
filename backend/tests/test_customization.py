"""Tests for architecture customization engine (was 12% covered)."""

from __future__ import annotations

from app.architecture.customization import customize_architecture
from app.domain.architecture import (
    CustomizationRequest,
    ReconstructedArchitecture,
    TechnologyBinding,
)
from app.domain.knowledge import KnowledgePackage


def _req(**kwargs) -> CustomizationRequest:
    return CustomizationRequest(**kwargs)


def _pkg_with_bindings(*concerns: str) -> KnowledgePackage:
    pkg = KnowledgePackage()
    pkg.reconstructed_architecture = ReconstructedArchitecture(
        technology_bindings=[
            TechnologyBinding(concern=c, selected="original", rationale="detected")
            for c in concerns
        ]
    )
    return pkg


def test_customize_replaces_backend_language():
    pkg = _pkg_with_bindings("backend-language")
    arch = customize_architecture(pkg, _req(backend_technology="FastAPI"))
    bindings = {b.concern: b.selected for b in arch.technology_bindings}
    assert bindings["backend-language"] == "FastAPI"


def test_customize_replaces_http_api():
    pkg = _pkg_with_bindings("http-api")
    arch = customize_architecture(pkg, _req(backend_technology="Express"))
    bindings = {b.concern: b.selected for b in arch.technology_bindings}
    assert bindings["http-api"] == "Express"


def test_customize_replaces_frontend():
    pkg = _pkg_with_bindings("frontend")
    arch = customize_architecture(pkg, _req(frontend_technology="Vue"))
    bindings = {b.concern: b.selected for b in arch.technology_bindings}
    assert bindings["frontend"] == "Vue"


def test_customize_replaces_persistence():
    pkg = _pkg_with_bindings("persistence")
    arch = customize_architecture(pkg, _req(database="MongoDB"))
    bindings = {b.concern: b.selected for b in arch.technology_bindings}
    assert bindings["persistence"] == "MongoDB"


def test_customize_adds_missing_backend_binding():
    pkg = KnowledgePackage()  # no bindings at all
    arch = customize_architecture(pkg, _req(backend_technology="Django"))
    assert any(b.selected == "Django" for b in arch.technology_bindings)


def test_customize_adds_missing_frontend_binding():
    pkg = KnowledgePackage()
    arch = customize_architecture(pkg, _req(frontend_technology="Svelte"))
    assert any(b.selected == "Svelte" for b in arch.technology_bindings)


def test_customize_adds_missing_db_binding():
    pkg = KnowledgePackage()
    arch = customize_architecture(pkg, _req(database="Redis"))
    assert any(b.selected == "Redis" for b in arch.technology_bindings)


def test_customize_adds_deployment_strategy():
    pkg = KnowledgePackage()
    arch = customize_architecture(pkg, _req(deployment_strategy="kubernetes"))
    assert any(b.concern == "deployment" and b.selected == "kubernetes" for b in arch.technology_bindings)


def test_customize_adds_authentication():
    pkg = KnowledgePackage()
    arch = customize_architecture(pkg, _req(authentication="OAuth2"))
    assert any(b.concern == "authentication" and b.selected == "OAuth2" for b in arch.technology_bindings)


def test_customize_appends_notes():
    pkg = KnowledgePackage()
    arch = customize_architecture(pkg, _req(notes="Use clean architecture"))
    assert "Use clean architecture" in arch.notes


def test_customize_empty_request_is_noop():
    pkg = _pkg_with_bindings("backend-language", "frontend")
    arch = customize_architecture(pkg, _req())
    # No changes should be made
    assert all(b.selected == "original" for b in arch.technology_bindings)
