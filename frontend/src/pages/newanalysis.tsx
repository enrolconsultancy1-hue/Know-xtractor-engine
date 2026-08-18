import { useState } from "react";
import { api } from "../api";
import { useAnalysisPoll } from "../hooks";
import type { ProjectCtx } from "../app";

const STAGES = [
  "repository_acquisition",
  "file_inventory",
  "language_detection",
  "static_analysis",
  "dependency_analysis",
  "api_discovery",
  "workflow_extraction",
  "architecture_discovery",
  "git_analysis",
  "knowledge_synthesis",
  "architecture_reconstruction",
];

export default function NewAnalysis({ onCreated }: { onCreated: (p: ProjectCtx) => void }) {
  const [url, setUrl] = useState("");
  const [name, setName] = useState("");
  const [branch, setBranch] = useState("main");
  const [depth, setDepth] = useState(3);
  const [analysisId, setAnalysisId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const status = useAnalysisPoll(analysisId);

  const create = async () => {
    setError("");
    try {
      const res = await api.createProject({ repository_url: url, name: name || undefined, branch });
      const a = await api.analyze(res.id, { branch });
      setAnalysisId(a.analysis_id);
      onCreated({ id: res.id, name: name || url.split("/").pop() || "project" });
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const done = status && ["done", "failed", "cancelled"].includes(status.status);

  return (
    <div>
      <h1>New Analysis</h1>
      <p className="subtitle">Submit a GitHub repository to extract its architectural knowledge.</p>

      <div className="card" style={{ maxWidth: 560 }}>
        <label>GitHub Repository URL</label>
        <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://github.com/owner/repo.git" />

        <label>Project Name (optional)</label>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="my-project" />

        <div className="grid cols-2">
          <div>
            <label>Branch</label>
            <input value={branch} onChange={(e) => setBranch(e.target.value)} />
          </div>
          <div>
            <label>Analysis Depth</label>
            <select value={depth} onChange={(e) => setDepth(Number(e.target.value))}>
              <option value={1}>1 — inventory only</option>
              <option value={2}>2 — inventory + structure</option>
              <option value={3}>3 — full (AST, APIs, workflows)</option>
            </select>
          </div>
        </div>

        <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
          <button className="btn" onClick={create} disabled={!url || !!analysisId}>Analyze</button>
        </div>
        {error && <p style={{ color: "var(--red)", fontSize: 13 }}>{error}</p>}
      </div>

      {status && (
        <div className="card" style={{ maxWidth: 560 }}>
          <h2>Analysis Progress</h2>
          <div className="progress"><div className="bar" style={{ width: `${Math.round(status.progress * 100)}%` }} /></div>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span className={`badge ${status.status === "done" ? "green" : status.status === "failed" ? "red" : "amber"}`}>{status.status}</span>
            <span className="mono">{Math.round(status.progress * 100)}%</span>
          </div>
          <div className="stage-list" style={{ marginTop: 10 }}>
            {STAGES.map((s) => (
              <div className="stage" key={s}>
                <span>{s.replace(/_/g, " ")}</span>
                <span className="mono" style={{ color: "var(--muted)" }}>{status.stage === s || status.stage === "done" ? "✓" : "·"}</span>
              </div>
            ))}
          </div>
          {status.errors.length > 0 && (
            <div style={{ marginTop: 10, color: "var(--red)", fontSize: 13 }}>
              {status.errors.map((e, i) => <div key={i}>⚠ {e}</div>)}
            </div>
          )}
          {done && <p className="subtitle" style={{ marginTop: 10 }}>Analysis finished. Navigate to Repository, Architecture, or Knowledge to inspect results.</p>}
        </div>
      )}
    </div>
  );
}
