// Shared types mirroring the backend knowledge model.

export interface Project {
  id: number;
  name: string;
  repository_url: string;
  status: string;
  last_run_status?: string | null;
  summary?: Record<string, unknown>;
}

export interface AnalysisStatus {
  id: number;
  project_id: number;
  status: string;
  stage: string;
  progress: number;
  errors: string[];
  warnings: string[];
  summary: Record<string, unknown>;
}

export interface Component {
  id: string;
  name: string;
  type: string;
  purpose: string;
  responsibilities: string[];
  dependencies: string[];
  consumers: string[];
  location: string;
  architectural_layer: string;
  confidence: { score: number };
}

export interface WorkflowStep {
  id: string;
  name: string;
  kind: string;
  component_id?: string;
  description: string;
  dependencies: string[];
}

export interface Workflow {
  id: string;
  name: string;
  entry_point: string;
  trigger: string;
  steps: WorkflowStep[];
  confidence: { score: number };
}

export interface ApiEndpoint {
  method: string;
  path: string;
  handler: string;
  file: string;
  framework: string;
}

export interface DataEntity {
  name: string;
  kind: string;
  columns: { name: string; type: string; primary_key: boolean; foreign_key: boolean }[];
  source_kind: string;
}

export interface Sprint {
  id: string;
  name: string;
  time_range: [string, string];
  objective: string;
  architectural_changes: string[];
}

export interface KnowledgePackage {
  metadata: Record<string, unknown>;
  technologies: {
    languages: { name: string; confidence: { score: number } }[];
    frameworks: { name: string }[];
    databases: { name: string }[];
    infrastructure: { name: string }[];
    dependencies: { name: string; purpose: string; architectural_layer: string; criticality: string }[];
  };
  architecture: {
    primary_pattern: string;
    confidence: number;
    patterns: { name: string; confidence: number }[];
    layers: { name: string; components: string[] }[];
  };
  components: Component[];
  workflows: Workflow[];
  data_model: { entities: DataEntity[]; relationships: { source: string; target: string; kind: string }[] };
  apis: { endpoints: ApiEndpoint[]; framework: string };
  architectural_sprints: { sprints: Sprint[] };
  facts: { fact: string; kind: string; confidence: number }[];
  risks: string[];
  reconstructed_architecture: {
    essential_capabilities: string[];
    domain_model: string[];
    technology_bindings: { concern: string; selected: string; rationale: string }[];
    principles: string[];
  };
  implementation_specification: {
    technology_stack: Record<string, string>;
    implementation_order: string[];
    acceptance_criteria: string[];
  };
}

export interface Graph {
  nodes: { id: string; type: string; label: string }[];
  edges: { source: string; target: string; relation: string }[];
}
