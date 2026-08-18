import type { ProjectCtx } from "../app";

export type PageKey =
  | "dashboard"
  | "new"
  | "repository"
  | "architecture"
  | "knowledge"
  | "sprints"
  | "designer"
  | "prompt";

const ITEMS: { key: PageKey; label: string }[] = [
  { key: "dashboard", label: "Dashboard" },
  { key: "new", label: "New Analysis" },
  { key: "repository", label: "Repository" },
  { key: "architecture", label: "Architecture" },
  { key: "knowledge", label: "Knowledge" },
  { key: "sprints", label: "Sprints" },
  { key: "designer", label: "Implementation" },
  { key: "prompt", label: "Prompt" },
];

export default function Sidebar({
  page,
  setPage,
  project,
}: {
  page: PageKey;
  setPage: (p: PageKey) => void;
  project: ProjectCtx | null;
}) {
  return (
    <div className="sidebar">
      <div className="brand">
        KNOX
        <small>Knowledge eXtraction</small>
      </div>
      {ITEMS.map((it) => (
        <button
          key={it.key}
          className={`nav-item ${page === it.key ? "active" : ""}`}
          onClick={() => setPage(it.key)}
        >
          <span>{it.label}</span>
        </button>
      ))}
      {project && (
        <div style={{ marginTop: "auto", fontSize: 12, color: "var(--muted)" }}>
          <div style={{ fontWeight: 600, color: "var(--text)" }}>{project.name}</div>
          <div className="mono">#{project.id}</div>
        </div>
      )}
    </div>
  );
}
