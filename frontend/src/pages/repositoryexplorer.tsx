import { useMemo } from "react";
import { useKnowledge } from "../hooks";
import type { ProjectCtx } from "../app";
import type { PageKey } from "../components/sidebar";

export default function RepositoryExplorer({
  project,
  setPage,
}: {
  project: ProjectCtx;
  setPage: (p: PageKey) => void;
}) {
  const { pkg, loading, error } = useKnowledge(project.id);

  const tree = useMemo(() => {
    if (!pkg) return [];
    const dirs = new Map<string, number>();
    pkg.components.forEach((c) => {
      const parts = c.location.split("/");
      parts.pop(); // drop filename
      let acc = "";
      parts.forEach((p) => {
        acc = acc ? `${acc}/${p}` : p;
        dirs.set(acc, (dirs.get(acc) || 0) + 1);
      });
    });
    return Array.from(dirs.entries()).sort((a, b) => a[0].localeCompare(b[0]));
  }, [pkg]);

  if (loading) return <p className="subtitle">Loading…</p>;
  if (error) return <div className="card"><p style={{ color: "var(--red)" }}>{error}</p><p className="subtitle">Run an analysis first (New Analysis).</p></div>;
  if (!pkg) return null;

  const langNames = pkg.technologies.languages.map((l) => l.name);
  const symbols = pkg.components.filter((c) => ["class", "function", "model", "service", "component"].includes(c.type));

  return (
    <div>
      <h1>Repository Explorer</h1>
      <p className="subtitle">{String(pkg.metadata.repository || "")} · {String(pkg.metadata.source_url || "")}</p>

      <div style={{ display: "flex", gap: 8, marginBottom: 14, flexWrap: "wrap" }}>
        <button className="btn secondary" onClick={() => setPage("architecture")}>Architecture →</button>
        <button className="btn secondary" onClick={() => setPage("knowledge")}>Knowledge →</button>
        <button className="btn secondary" onClick={() => setPage("sprints")}>Sprints →</button>
      </div>

      <div className="grid cols-3">
        <div className="card">
          <h2>Languages</h2>
          {langNames.map((l) => <span key={l} className="chip">{l}</span>)}
          <h2>Frameworks</h2>
          {pkg.technologies.frameworks.map((f) => <span key={f.name} className="chip">{f.name}</span>)}
          <h2>Databases</h2>
          {pkg.technologies.databases.map((d) => <span key={d.name} className="chip">{d.name}</span>)}
          <h2>Infrastructure</h2>
          {pkg.technologies.infrastructure.map((i) => <span key={i.name} className="chip">{i.name}</span>)}
        </div>

        <div className="card">
          <h2>Directory Tree</h2>
          <div className="mono" style={{ maxHeight: 320, overflowY: "auto" }}>
            {tree.map(([dir, count]) => (
              <div key={dir}>📁 {dir} <span style={{ color: "var(--muted)" }}>({count})</span></div>
            ))}
          </div>
        </div>

        <div className="card">
          <h2>Dependencies</h2>
          <table>
            <thead><tr><th>Name</th><th>Layer</th><th>Criticality</th></tr></thead>
            <tbody>
              {pkg.technologies.dependencies.slice(0, 30).map((d) => (
                <tr key={d.name}>
                  <td className="mono">{d.name}</td>
                  <td>{d.architectural_layer}</td>
                  <td><span className={`badge ${d.criticality === "critical" ? "red" : d.criticality === "major" ? "amber" : "gray"}`}>{d.criticality}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <h2>Symbols ({symbols.length})</h2>
        <table>
          <thead><tr><th>Symbol</th><th>Type</th><th>Layer</th><th>Location</th><th>Purpose</th></tr></thead>
          <tbody>
            {symbols.slice(0, 200).map((s) => (
              <tr key={s.id}>
                <td className="mono">{s.name}</td>
                <td><span className="badge blue">{s.type}</span></td>
                <td>{s.architectural_layer}</td>
                <td className="mono">{s.location}</td>
                <td style={{ color: "var(--muted)" }}>{s.purpose.slice(0, 80)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
