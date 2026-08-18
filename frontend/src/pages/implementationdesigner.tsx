import { useState } from "react";
import { api } from "../api";
import { useKnowledge } from "../hooks";
import type { ProjectCtx } from "../app";

const FIELDS = [
  { key: "frontend_technology", label: "Frontend Technology" },
  { key: "backend_technology", label: "Backend Technology" },
  { key: "database", label: "Database" },
  { key: "deployment_strategy", label: "Deployment Strategy" },
  { key: "architecture_pattern", label: "Architecture Pattern" },
  { key: "authentication", label: "Authentication" },
  { key: "infrastructure", label: "Infrastructure" },
];

export default function ImplementationDesigner({ project }: { project: ProjectCtx }) {
  const { pkg, loading, error, reload } = useKnowledge(project.id);
  const [form, setForm] = useState<Record<string, string>>({});
  const [message, setMessage] = useState("");

  if (loading) return <p className="subtitle">Loading…</p>;
  if (error || !pkg) return <div className="card"><p style={{ color: "var(--red)" }}>{error}</p></div>;

  const apply = async () => {
    const body = Object.fromEntries(Object.entries(form).filter(([, v]) => v.trim()));
    if (!Object.keys(body).length) {
      setMessage("Select at least one technology to substitute.");
      return;
    }
    try {
      await api.customize(project.id, body);
      setMessage("Architecture customized. Regenerated implementation specification.");
      setForm({});
      reload();
    } catch (e) {
      setMessage((e as Error).message);
    }
  };

  return (
    <div>
      <h1>Implementation Designer</h1>
      <p className="subtitle">Change the technology binding without disturbing the knowledge layer.</p>

      <div className="grid cols-2">
        <div className="card">
          <h2>Current Bindings</h2>
          <table>
            <thead><tr><th>Concern</th><th>Selected</th></tr></thead>
            <tbody>
              {pkg.reconstructed_architecture.technology_bindings.map((b) => (
                <tr key={b.concern}>
                  <td>{b.concern}</td>
                  <td><span className="badge blue">{b.selected}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card">
          <h2>Customize</h2>
          {FIELDS.map((f) => (
            <div key={f.key}>
              <label>{f.label}</label>
              <input
                value={form[f.key] || ""}
                placeholder="e.g. Django, PostgreSQL, Docker…"
                onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
              />
            </div>
          ))}
          <button className="btn" onClick={apply}>Regenerate Architecture</button>
          {message && <p className="subtitle" style={{ marginTop: 8 }}>{message}</p>}
        </div>
      </div>

      <div className="card">
        <h2>Essential Capabilities (knowledge layer — stable)</h2>
        {pkg.reconstructed_architecture.essential_capabilities.map((c) => <div key={c}>• {c}</div>)}
      </div>

      <div className="card">
        <h2>Implementation Order</h2>
        {pkg.implementation_specification.implementation_order.map((s) => <div key={s}>• {s}</div>)}
      </div>
    </div>
  );
}
