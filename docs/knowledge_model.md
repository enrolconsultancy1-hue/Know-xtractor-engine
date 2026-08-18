# Knowledge Model

The canonical output of KNOX is the `KnowledgePackage` (Pydantic model in
`backend/app/domain/knowledge.py`). It is deliberately **independent of the
original repository** — it contains understanding and evidence references, not
source code.

## Canonical schema

```
KnowledgePackage
├── metadata                    # repository, source_url, generated_at, schema_version
├── technologies                # TechnologyStack: languages, frameworks, databases,
│                               #   infrastructure, dependencies (with purpose/criticality)
├── architecture                # ArchitectureReport: patterns, confidence, layers, entry points
├── components                  # Component[]: id, name, type, purpose, deps, layer, evidence
├── workflows                   # Workflow[]: steps, trigger, entry point, error paths
├── data_model                  # DataModel: entities, columns, relationships, engines
├── apis                        # ApiSpec: endpoints (method/path/handler), framework
├── integrations                # external service/package hints
├── configuration               # redacted config keys + secret_required
├── testing                     # per-file test signals (behavioral evidence)
├── security                    # secret count, execution policy
├── architectural_sprints       # EvolutionTimeline: sprints + facts/inferences
├── architectural_decisions     # extracted decisions
├── invariants / constraints / patterns / anti_patterns / risks / assumptions
├── facts                       # KnowledgeFact[]: fact, kind, confidence, evidence
├── evidence                    # aggregate evidence index
├── implementation_specification# ImplementationSpec (all sections)
└── reconstructed_architecture  # ReconstructedArchitecture (technology-neutral + bindings)
```

## Evidence & classification

Every important statement carries:

- `confidence` (0.0–1.0) and, where relevant, `evidence` (file/symbol/reason).
- a `kind` of **fact** | **inference** | **hypothesis**.

Example:

```json
{
  "id": "fact-003",
  "fact": "The system follows a Modular Monolith architecture",
  "kind": "inference",
  "confidence": 0.8,
  "evidence": [
    { "file": "(repo)", "reason": "evidence-weighted pattern scoring" }
  ]
}
```

## Layering

The model enforces the separation between:

1. **Knowledge layer** — domain concepts, capabilities, workflows (stable).
2. **Architecture layer** — components, layers, patterns, relationships.
3. **Technology binding layer** — concerns mapped to concrete tech
   (`ReconstructedArchitecture.technology_bindings`).
4. **Implementation plan** — `ImplementationSpec`, renderable as a prompt.

Customizing technology (e.g. FastAPI → Django) only rewrites layer 3 and
re-generates the implementation plan; layers 1 and 2 remain stable.

## Serialization

- **JSON** — canonical (`KnowledgePackage.model_dump_json`).
- **YAML / Markdown / PDF** — human-readable renders (`services/exporter.py`).
