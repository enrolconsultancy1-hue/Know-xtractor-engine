import { useEffect, useState } from "react";
import { api } from "../api";
import { useKnowledge } from "../hooks";
import type { ProjectCtx } from "../app";

export default function PromptGenerator({ project }: { project: ProjectCtx }) {
  const { pkg, loading, error } = useKnowledge(project.id);
  const [prompt, setPrompt] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (pkg) {
      api.implementationPrompt(project.id).then((r) => setPrompt(r.prompt)).catch(() => {});
    }
  }, [pkg, project.id]);

  const copy = async () => {
    await navigator.clipboard.writeText(prompt);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  if (loading) return <p className="subtitle">Loading…</p>;
  if (error || !pkg) return <div className="card"><p style={{ color: "var(--red)" }}>{error}</p></div>;

  return (
    <div>
      <h1>Implementation Prompt</h1>
      <p className="subtitle">One prompt, detailed enough for another coding agent to implement the system.</p>

      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <button className="btn" onClick={copy}>{copied ? "Copied ✓" : "Copy"}</button>
        <button
          className="btn secondary"
          onClick={() => {
            const blob = new Blob([prompt], { type: "text/markdown" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `${project.name}-implementation-prompt.md`;
            a.click();
            URL.revokeObjectURL(url);
          }}
        >
          Export Markdown
        </button>
      </div>

      <pre className="prompt">{prompt || "Generating…"}</pre>
    </div>
  );
}
