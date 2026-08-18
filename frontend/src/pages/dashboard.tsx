import { useEffect, useState } from "react";
import { api } from "../api";
import type { Project } from "../types";
import type { ProjectCtx } from "../app";

export default function Dashboard({ openProject }: { openProject: (p: ProjectCtx, t?: any) => void }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .listProjects()
      .then(setProjects)
      .finally(() => setLoading(false));
  }, []);

  const statusBadge = (s?: string | null) => {
    const map: Record<string, string> = { done: "green", running: "amber", failed: "red", created: "gray", cancelled: "gray" };
    return <span className={`badge ${map[s || "created"] || "gray"}`}>{s || "created"}</span>;
  };

  return (
    <div>
      <h1>Dashboard</h1>
      <p className="subtitle">Repository → Pure Knowledge → Architecture → Implementation-Ready Prompt</p>

      <div className="grid cols-4">
        <div className="stat"><div className="value">{projects.length}</div><div className="label">Projects</div></div>
        <div className="stat"><div className="value">{projects.filter((p) => p.last_run_status === "done").length}</div><div className="label">Analyzed</div></div>
        <div className="stat"><div className="value">{projects.filter((p) => p.last_run_status === "running").length}</div><div className="label">Running</div></div>
        <div className="stat"><div className="value">{projects.filter((p) => p.last_run_status === "failed").length}</div><div className="label">Failed</div></div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <h2>Projects</h2>
        {loading ? (
          <p className="subtitle">Loading…</p>
        ) : projects.length === 0 ? (
          <p className="subtitle">No projects yet. Start a New Analysis to submit a GitHub repository.</p>
        ) : (
          <table>
            <thead><tr><th>Name</th><th>Repository</th><th>Status</th><th>Architecture</th><th></th></tr></thead>
            <tbody>
              {projects.map((p) => (
                <tr key={p.id}>
                  <td>{p.name}</td>
                  <td className="mono">{p.repository_url}</td>
                  <td>{statusBadge(p.last_run_status)}</td>
                  <td>{(p.summary as any)?.primary_pattern || "—"}</td>
                  <td>
                    <button className="btn secondary" onClick={() => openProject({ id: p.id, name: p.name }, "repository")}>
                      Open
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
