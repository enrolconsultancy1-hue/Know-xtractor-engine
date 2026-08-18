import { useKnowledge } from "../hooks";
import { ComponentDiagram, DataModelDiagram, LayerDiagram, WorkflowDiagram } from "../components/diagrams";
import type { ProjectCtx } from "../app";

export default function ArchitectureView({ project }: { project: ProjectCtx }) {
  const { pkg, loading, error } = useKnowledge(project.id);
  if (loading) return <p className="subtitle">Loading…</p>;
  if (error || !pkg) return <div className="card"><p style={{ color: "var(--red)" }}>{error}</p></div>;

  const arch = pkg.architecture;
  return (
    <div>
      <h1>Architecture View</h1>
      <p className="subtitle">
        Primary pattern: <b>{arch.primary_pattern || "undetermined"}</b> · confidence {arch.confidence.toFixed(2)}
      </p>

      <div className="grid cols-3">
        {arch.patterns.map((p) => (
          <div className="card" key={p.name}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <b>{p.name}</b>
              <span className="badge blue">{(p.confidence * 100).toFixed(0)}%</span>
            </div>
            <div className="progress" style={{ marginTop: 8 }}><div className="bar" style={{ width: `${p.confidence * 100}%` }} /></div>
          </div>
        ))}
      </div>

      <div className="card">
        <h2>Component Architecture</h2>
        <ComponentDiagram components={pkg.components} />
      </div>

      <div className="card">
        <h2>Architectural Layers</h2>
        <LayerDiagram layers={arch.layers} />
      </div>

      <div className="card">
        <h2>Data Model</h2>
        {pkg.data_model.entities.length ? (
          <DataModelDiagram entities={pkg.data_model.entities} />
        ) : (
          <p className="subtitle">No data entities detected.</p>
        )}
      </div>

      <div className="card">
        <h2>Workflows</h2>
        {pkg.workflows.length ? (
          pkg.workflows.slice(0, 3).map((w) => (
            <div key={w.id} style={{ marginBottom: 18 }}>
              <h2 style={{ margin: "0 0 6px" }}>{w.name} <span className="badge gray">{w.trigger}</span></h2>
              <WorkflowDiagram workflow={w} />
            </div>
          ))
        ) : (
          <p className="subtitle">No workflows reconstructed.</p>
        )}
      </div>

      <div className="card">
        <h2>API Topology ({pkg.apis.endpoints.length})</h2>
        <table>
          <thead><tr><th>Method</th><th>Path</th><th>Handler</th><th>File</th></tr></thead>
          <tbody>
            {pkg.apis.endpoints.map((e, i) => (
              <tr key={i}>
                <td><span className="badge green">{e.method.toUpperCase()}</span></td>
                <td className="mono">{e.path}</td>
                <td>{e.handler}</td>
                <td className="mono">{e.file}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
