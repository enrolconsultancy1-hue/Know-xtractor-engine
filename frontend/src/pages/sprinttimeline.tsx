import { useKnowledge } from "../hooks";
import type { ProjectCtx } from "../app";

export default function SprintTimeline({ project }: { project: ProjectCtx }) {
  const { pkg, loading, error } = useKnowledge(project.id);
  if (loading) return <p className="subtitle">Loading…</p>;
  if (error || !pkg) return <div className="card"><p style={{ color: "var(--red)" }}>{error}</p></div>;

  const sprints = pkg.architectural_sprints.sprints;
  return (
    <div>
      <h1>Architectural Evolution</h1>
      <p className="subtitle">Sprints clustered from git history (time + topic).</p>
      {sprints.length === 0 ? (
        <p className="subtitle">No git history available for this repository.</p>
      ) : (
        <div>
          {sprints.map((s, i) => (
            <div className="card" key={s.id} style={{ position: "relative", paddingLeft: 40 }}>
              <div style={{ position: "absolute", left: 12, top: 20, width: 14, height: 14, borderRadius: 999, background: "var(--accent)" }} />
              {i < sprints.length - 1 && <div style={{ position: "absolute", left: 18, top: 34, bottom: -16, width: 2, background: "var(--border)" }} />}
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <b>{s.id}: {s.name}</b>
                <span className="mono" style={{ color: "var(--muted)", fontSize: 12 }}>{s.time_range[0].slice(0, 10)} → {s.time_range[1].slice(0, 10)}</span>
              </div>
              <p style={{ color: "var(--muted)", fontSize: 13 }}>{s.objective}</p>
              {s.architectural_changes.length > 0 && (
                <div style={{ fontSize: 13 }}>
                  {s.architectural_changes.map((c, j) => <div key={j}>• {c}</div>)}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
