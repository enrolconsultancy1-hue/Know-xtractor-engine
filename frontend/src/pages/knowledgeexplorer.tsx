import { useState } from "react";
import { useKnowledge } from "../hooks";
import type { ProjectCtx } from "../app";

const TABS = ["Technologies", "Components", "Workflows", "Patterns", "Facts", "APIs", "Data Model", "Risks"] as const;

export default function KnowledgeExplorer({ project }: { project: ProjectCtx }) {
  const { pkg, loading, error } = useKnowledge(project.id);
  const [tab, setTab] = useState<(typeof TABS)[number]>("Technologies");
  if (loading) return <p className="subtitle">Loading…</p>;
  if (error || !pkg) return <div className="card"><p style={{ color: "var(--red)" }}>{error}</p></div>;

  return (
    <div>
      <h1>Knowledge Explorer</h1>
      <p className="subtitle">Navigate the extracted, source-independent knowledge.</p>

      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 14 }}>
        {TABS.map((t) => (
          <button key={t} className={`btn ${tab === t ? "" : "secondary"}`} onClick={() => setTab(t)}>{t}</button>
        ))}
      </div>

      {tab === "Technologies" && (
        <div className="card">
          <h2>Technology Stack</h2>
          {(["languages", "frameworks", "databases", "infrastructure"] as const).map((k) => (
            <div key={k} style={{ marginBottom: 8 }}>
              <b>{k}:</b>{" "}
              {(pkg.technologies[k] as any[]).map((t) => (
                <span key={t.name} className="chip">{t.name}</span>
              ))}
            </div>
          ))}
          <h2>Dependencies</h2>
          <table>
            <thead><tr><th>Name</th><th>Purpose</th><th>Layer</th><th>Criticality</th></tr></thead>
            <tbody>
              {pkg.technologies.dependencies.map((d) => (
                <tr key={d.name}>
                  <td className="mono">{d.name}</td>
                  <td>{d.purpose}</td>
                  <td>{d.architectural_layer}</td>
                  <td>{d.criticality}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "Components" && (
        <div className="card">
          <h2>Components ({pkg.components.length})</h2>
          <table>
            <thead><tr><th>Name</th><th>Type</th><th>Layer</th><th>Responsibilities</th><th>Dependencies</th></tr></thead>
            <tbody>
              {pkg.components.map((c) => (
                <tr key={c.id}>
                  <td className="mono">{c.name}</td>
                  <td><span className="badge blue">{c.type}</span></td>
                  <td>{c.architectural_layer}</td>
                  <td style={{ color: "var(--muted)" }}>{c.responsibilities.slice(0, 2).join(", ")}</td>
                  <td className="mono" style={{ color: "var(--muted)" }}>{c.dependencies.slice(0, 4).join(", ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "Workflows" && (
        <div className="card">
          {pkg.workflows.map((w) => (
            <div key={w.id} style={{ marginBottom: 14 }}>
              <b>{w.name}</b> <span className="badge gray">{w.trigger}</span>
              <div style={{ marginTop: 4, color: "var(--muted)", fontSize: 13 }}>
                {w.steps.map((s) => s.name).join(" → ")}
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === "Patterns" && (
        <div className="card">
          <h2>Architecture Patterns</h2>
          {pkg.architecture.patterns.map((p) => (
            <div key={p.name} style={{ marginBottom: 8 }}>
              <b>{p.name}</b> — confidence {(p.confidence * 100).toFixed(0)}%
            </div>
          ))}
          <h2>Reconstruction Principles</h2>
          {pkg.reconstructed_architecture.principles.map((p) => <div key={p}>• {p}</div>)}
        </div>
      )}

      {tab === "Facts" && (
        <div className="card">
          <h2>Facts / Inferences / Hypotheses</h2>
          {pkg.facts.map((f, i) => (
            <div key={i} style={{ display: "flex", gap: 8, padding: "6px 0", borderBottom: "1px solid var(--border)" }}>
              <span className={`badge ${f.kind === "fact" ? "green" : f.kind === "inference" ? "blue" : "amber"}`}>{f.kind.toUpperCase()}</span>
              <span style={{ flex: 1 }}>{f.fact}</span>
              <span className="mono" style={{ color: "var(--muted)" }}>{(f.confidence * 100).toFixed(0)}%</span>
            </div>
          ))}
        </div>
      )}

      {tab === "APIs" && (
        <div className="card">
          <h2>API Specification</h2>
          {pkg.apis.endpoints.map((e, i) => (
            <div key={i} className="mono" style={{ padding: "4px 0" }}>
              <span className="badge green">{e.method.toUpperCase()}</span> {e.path} → {e.handler}
            </div>
          ))}
        </div>
      )}

      {tab === "Data Model" && (
        <div className="card">
          <h2>Entities</h2>
          {pkg.data_model.entities.map((e) => (
            <div key={e.name} style={{ marginBottom: 8 }}>
              <b>{e.name}</b> <span className="badge gray">{e.source_kind}</span>
              <div className="mono" style={{ color: "var(--muted)", fontSize: 12 }}>
                {e.columns.map((c) => `${c.name}:${c.type}`).join(", ")}
              </div>
            </div>
          ))}
          <h2>Relationships</h2>
          {pkg.data_model.relationships.map((r, i) => (
            <div key={i} className="mono">{r.source} {r.kind} {r.target}</div>
          ))}
        </div>
      )}

      {tab === "Risks" && (
        <div className="card">
          <h2>Risks</h2>
          {pkg.risks.map((r) => <div key={r}>⚠ {r}</div>)}
        </div>
      )}
    </div>
  );
}
