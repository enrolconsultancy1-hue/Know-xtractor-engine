import { useState, useEffect } from "react";
import { getAuthToken, setAuthToken } from "../api";

export default function Settings() {
  const [token, setToken] = useState("");
  const [saved, setSaved] = useState(false);
  const [healthStatus, setHealthStatus] = useState<string>("Checking...");
  const [readyStatus, setReadyStatus] = useState<string>("Checking...");
  const [authStatus, setAuthStatus] = useState<{ checked: boolean; ok: boolean; msg: string }>({
    checked: false,
    ok: true,
    msg: "",
  });

  useEffect(() => {
    setToken(getAuthToken());
    checkBackendHealth();
  }, []);

  const checkBackendHealth = async () => {
    try {
      const h = await fetch("/api/health");
      if (h.ok) {
        const data = await h.json();
        setHealthStatus(`Connected (${data.app} v${data.version})`);
      } else {
        setHealthStatus(`Error: ${h.status}`);
      }
    } catch (e: any) {
      setHealthStatus(`Offline (${e.message})`);
    }

    try {
      const r = await fetch("/readyz");
      if (r.ok) {
        setReadyStatus("Ready (DB & Queue connected)");
      } else {
        const data = await r.json().catch(() => ({}));
        setReadyStatus(`Not Ready (${data.detail || r.status})`);
      }
    } catch (e: any) {
      setReadyStatus(`Unavailable (${e.message})`);
    }
  };

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    setAuthToken(token);
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
    testAuth(token);
  };

  const handleClear = () => {
    setToken("");
    setAuthToken("");
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
    testAuth("");
  };

  const testAuth = async (candidateToken: string) => {
    try {
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (candidateToken.trim()) {
        headers["Authorization"] = `Bearer ${candidateToken.trim()}`;
      }
      // Test GET /projects (reads are allowed or token verified)
      const res = await fetch("/api/projects", { headers });
      if (res.ok) {
        setAuthStatus({
          checked: true,
          ok: true,
          msg: candidateToken.trim()
            ? "API Key successfully validated against the backend."
            : "Connected with open (none) auth mode.",
        });
      } else if (res.status === 401) {
        setAuthStatus({
          checked: true,
          ok: false,
          msg: "401 Unauthorized: The server rejected this API Key or requires one.",
        });
      } else {
        setAuthStatus({
          checked: true,
          ok: false,
          msg: `HTTP ${res.status}: Unexpected response.`,
        });
      }
    } catch (e: any) {
      setAuthStatus({ checked: true, ok: false, msg: `Connection error: ${e.message}` });
    }
  };

  return (
    <div>
      <h1>Settings & Authentication</h1>
      <p className="subtitle">
        Manage API credentials and verify backend service connectivity.
      </p>

      <div className="card">
        <h2>API Authentication Key</h2>
        <p className="subtitle" style={{ marginBottom: 12 }}>
          When KNOX runs with <span className="mono">KNOX_AUTH_MODE=token</span> (e.g. in Docker Compose or production),
          mutating requests (creating projects, launching analyses, customizing architectures) require a Bearer token.
        </p>

        <form onSubmit={handleSave} style={{ maxWidth: 540 }}>
          <div style={{ marginBottom: 12 }}>
            <label style={{ display: "block", fontSize: 13, marginBottom: 6, color: "var(--muted)" }}>
              Bearer Token / API Key
            </label>
            <input
              type="password"
              placeholder="Paste your KNOX_API_KEY here..."
              value={token}
              onChange={(e) => setToken(e.target.value)}
              className="mono"
            />
          </div>

          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <button type="submit" className="btn btn-primary">
              Save API Key
            </button>
            {token && (
              <button type="button" onClick={handleClear} className="btn btn-secondary">
                Clear
              </button>
            )}
            <button type="button" onClick={() => testAuth(token)} className="btn btn-secondary">
              Test Connection
            </button>
            {saved && <span className="badge green">Saved</span>}
          </div>
        </form>

        {authStatus.checked && (
          <div style={{ marginTop: 16 }}>
            <span className={`badge ${authStatus.ok ? "green" : "red"}`}>
              {authStatus.ok ? "Authentication OK" : "Authentication Failed"}
            </span>
            <span style={{ fontSize: 13, marginLeft: 10, color: "var(--muted)" }}>
              {authStatus.msg}
            </span>
          </div>
        )}
      </div>

      <div className="card">
        <h2>Backend Connectivity</h2>
        <div style={{ display: "grid", gridTemplateColumns: "140px 1fr", rowGap: 10, fontSize: 13 }}>
          <div style={{ color: "var(--muted)" }}>API Health:</div>
          <div>
            <span className="mono">{healthStatus}</span>
          </div>
          <div style={{ color: "var(--muted)" }}>Readiness:</div>
          <div>
            <span className="mono">{readyStatus}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
