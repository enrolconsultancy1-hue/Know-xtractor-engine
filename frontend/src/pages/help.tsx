import { useState, type ReactNode } from "react";

type InstallTab = "backend" | "frontend" | "docker";

const INSTALL_TABS: { key: InstallTab; label: string }[] = [
  { key: "backend", label: "1 · Backend API" },
  { key: "frontend", label: "2 · Web UI" },
  { key: "docker", label: "Alternative · Docker" },
];

function Cmd({ children }: { children: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="cmd">
      <code className="mono">{children}</code>
      <button
        className="cmd-copy"
        title="Copy to clipboard"
        onClick={() => {
          navigator.clipboard?.writeText(children).catch(() => {});
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        }}
      >
        {copied ? "copied" : "copy"}
      </button>
    </div>
  );
}

function Step({ n, title, children }: { n: number; title: string; children?: ReactNode }) {
  return (
    <div className="step">
      <div className="step-num">{n}</div>
      <div>
        <strong>{title}</strong>
        {children && <div style={{ marginTop: 6 }}>{children}</div>}
      </div>
    </div>
  );
}

const BACKEND_STEPS = [
  {
    title: "Install Python 3.11+",
    body: <p className="subtitle">Check with <span className="mono">python --version</span>. Get it from python.org if needed.</p>,
  },
  {
    title: "Create a virtualenv and install dependencies",
    cmd: "cd backend\npython -m venv .venv\n.venv\\Scripts\\activate\npip install -r requirements.txt",
    note: "On macOS/Linux activate with: source .venv/bin/activate",
  },
  {
    title: "Verify your machine is ready",
    cmd: "python -m app.cli doctor",
    note: "Every check should print OK. Failed checks print the exact fix.",
  },
  {
    title: "Run migrations and start the API",
    cmd: "alembic upgrade head\nuvicorn app.main:app --reload --port 8000",
    note: "Interactive API docs: http://127.0.0.1:8000/docs. Dev defaults need no configuration; edit backend/.env (see .env.example) for Postgres, auth tokens, and limits.",
  },
];

const FRONTEND_STEPS = [
  {
    title: "Install Node.js 20+",
    body: <p className="subtitle">Check with <span className="mono">node --version</span>.</p>,
  },
  {
    title: "Install dependencies and start the dev server",
    cmd: "cd frontend\nnpm install\nnpm run dev",
    note: "Open http://localhost:5173 — it proxies /api calls to the backend on port 8000.",
  },
  {
    title: "You are ready",
    body: <p className="subtitle">Keep both terminals running, then follow “Using KNOX” below.</p>,
  },
];

const DOCKER_STEPS = [
  {
    title: "Create a .env next to docker-compose.yml",
    cmd: "POSTGRES_PASSWORD=choose-a-strong-password\nKNOX_API_KEY=choose-a-long-random-token",
  },
  {
    title: "Start the full stack",
    cmd: "docker compose up --build",
    note: "Brings up Postgres, Redis, the API (with migrations applied), a worker, and the web UI.",
  },
  {
    title: "Verify",
    cmd: "curl http://localhost:8000/healthz",
    note: "Web UI on http://localhost:8080 · API on :8000 · HTTPS guide in docs/deployment.md.",
  },
];

export default function Help() {
  const [tab, setTab] = useState<InstallTab>("backend");
  const steps = tab === "backend" ? BACKEND_STEPS : tab === "frontend" ? FRONTEND_STEPS : DOCKER_STEPS;

  return (
    <div>
      <h1>Help</h1>
      <p className="subtitle">Install, run, and use KNOX — step by step.</p>

      <div className="card">
        <h2>Installation</h2>
        <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
          {INSTALL_TABS.map((t) => (
            <button
              key={t.key}
              className={`chip ${tab === t.key ? "active" : ""}`}
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>
        {steps.map((s, i) => (
          <Step key={i} n={i + 1} title={s.title}>
            {"body" in s && s.body}
            {"cmd" in s && s.cmd && <Cmd>{s.cmd}</Cmd>}
            {"note" in s && s.note && <p className="subtitle">{s.note}</p>}
          </Step>
        ))}
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <h2>Using KNOX</h2>
        <Step n={1} title="Submit a repository">
          <p className="subtitle">
            Go to <strong>New Analysis</strong>, paste a GitHub URL, pick a branch, and press Analyze.
            Progress streams through all analysis stages.
          </p>
        </Step>
        <Step n={2} title="Explore the Repository page">
          <p className="subtitle">Inventory of every analyzed file — sources, configs, tests, docs.</p>
        </Step>
        <Step n={3} title="Read the Architecture & Knowledge pages">
          <p className="subtitle">
            The reconstructed architecture pattern, components, APIs, data model, and workflows — each
            backed by evidence and classified as fact / inference / hypothesis.
          </p>
        </Step>
        <Step n={4} title="Review history in Sprints">
          <p className="subtitle">Git commits clustered into architectural sprints show how the system evolved.</p>
        </Step>
        <Step n={5} title="Design & generate your rebuild prompt">
          <p className="subtitle">
            In <strong>Implementation</strong>, customize the target tech stack. In <strong>Prompt</strong>,
            generate the single implementation-ready prompt for rebuilding the system.
          </p>
        </Step>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <h2>Troubleshooting</h2>
        <table>
          <thead><tr><th>Symptom</th><th>Fix</th></tr></thead>
          <tbody>
            <tr><td className="mono">401 Unauthorized</td><td>The API runs with <span className="mono">KNOX_AUTH_MODE=token</span> — send the token as a Bearer header, or set auth mode to none for local dev.</td></tr>
            <tr><td className="mono">503 Service Unavailable</td><td>Database or Redis is down / not migrated. Run <span className="mono">python -m app.cli doctor</span>.</td></tr>
            <tr><td className="mono">429 Rate limit exceeded</td><td>Too many requests — wait or raise <span className="mono">KNOX_RATE_LIMIT_REQUESTS</span>.</td></tr>
            <tr><td>Analysis stuck or failed</td><td>Check the run status on the Dashboard, then the backend logs (<span className="mono">docs/runbook.md</span> covers common failures).</td></tr>
          </tbody>
        </table>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <h2>Learn more</h2>
        <p className="subtitle">
          <span className="mono">docs/QUICKSTART.md</span> · <span className="mono">docs/ARCHITECTURE.md</span> ·{" "}
          <span className="mono">docs/API.md</span> · <span className="mono">docs/RUNBOOK.md</span> ·{" "}
          <span className="mono">docs/deployment.md</span> · <span className="mono">docs/SECURITY.md</span>
        </p>
      </div>
    </div>
  );
}
