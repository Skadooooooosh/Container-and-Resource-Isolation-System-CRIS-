import { useState } from "react";
import { api } from "../services/api";
import { Err, usePoll } from "../usePoll";

export default function Diagnostics() {
  const [filter, setFilter] = useState("ALL");
  const d = usePoll(() => api("/system/capabilities?refresh=true"), null);

  const features = d.data?.features ?? [];
  const filtered = features.filter((f: any) => {
    if (filter === "ALL") return true;
    if (filter === "ACTIVE") return f.status === "active";
    if (filter === "BLOCKED") return f.status === "blocked";
    if (filter === "UNSUPPORTED") return f.status === "unsupported";
    if (filter === "NOT_CONFIGURED") return f.status === "supported_not_configured";
    return true;
  });

  return (
    <>
      <div className="card-header">
        <h2>System Diagnostics & Kernel Capabilities</h2>
        <button className="btn sm primary" onClick={d.reload} disabled={d.loading}>
          {d.loading ? "Probing Kernel…" : "Re-run Live Probes"}
        </button>
      </div>

      <p style={{ color: "var(--text-muted)", marginTop: "-8px", marginBottom: "18px" }}>
        Every status reported below is obtained by executing a real Linux probe (such as <code>cris_run --probe</code> or
        inspecting <code>/sys/fs/cgroup</code>). Nothing is simulated or hardcoded.
      </p>

      <Err msg={d.error} />

      {/* Host Environment Overview */}
      {d.data?.environment && (
        <div className="card" style={{ marginBottom: "20px" }}>
          <h4 className="card-title" style={{ marginBottom: "12px" }}>
            Host Execution Environment
          </h4>
          <div className="metrics-grid">
            <div className="metric-card">
              <span className="metric-label">Operating System</span>
              <span className="metric-value" style={{ fontSize: "16px" }}>
                {d.data.environment.system}
              </span>
              <span className="metric-sub">Kernel: {d.data.environment.kernel}</span>
            </div>
            <div className="metric-card">
              <span className="metric-label">Architecture</span>
              <span className="metric-value" style={{ fontSize: "16px" }}>
                {d.data.environment.arch}
              </span>
              <span className="metric-sub">{d.data.environment.cpus} Cores</span>
            </div>
            <div className="metric-card">
              <span className="metric-label">Privilege / EUID</span>
              <span className="metric-value" style={{ fontSize: "16px" }}>
                {d.data.environment.euid != null ? `UID ${d.data.environment.euid}` : "N/A"}
              </span>
              <span className="metric-sub">
                {d.data.environment.euid === 0 ? "Root Privileged" : "Unprivileged User"}
              </span>
            </div>
            <div className="metric-card">
              <span className="metric-label">WSL2 Subsystem</span>
              <span className="metric-value" style={{ fontSize: "16px" }}>
                {d.data.environment.wsl ? "WSL2 Active" : "Native Linux / VM"}
              </span>
              <span className="metric-sub">Python {d.data.environment.python}</span>
            </div>
          </div>
        </div>
      )}

      {/* Filter Tabs */}
      <div style={{ display: "flex", gap: "8px", marginBottom: "12px", alignItems: "center" }}>
        <span style={{ fontSize: "12px", color: "var(--text-muted)", fontWeight: 600 }}>Filter:</span>
        {[
          { id: "ALL", label: `All (${features.length})` },
          { id: "ACTIVE", label: "Active" },
          { id: "BLOCKED", label: "Permission Blocked" },
          { id: "NOT_CONFIGURED", label: "Not Configured" },
          { id: "UNSUPPORTED", label: "Unsupported" },
        ].map((btn) => (
          <button
            key={btn.id}
            className={`btn sm ${filter === btn.id ? "primary" : ""}`}
            onClick={() => setFilter(btn.id)}
          >
            {btn.label}
          </button>
        ))}
      </div>

      {/* Capabilities Table */}
      <div className="table-wrap">
        {filtered.length ? (
          <table>
            <thead>
              <tr>
                <th>Feature / Subsystem</th>
                <th>Status</th>
                <th>Kernel Probe Details & Remediation</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((f: any) => (
                <tr key={f.id}>
                  <td>
                    <div style={{ fontWeight: 600 }}>{f.name}</div>
                    <div className="mono" style={{ fontSize: "10.5px", color: "var(--text-dim)" }}>
                      {f.id}
                    </div>
                  </td>
                  <td>
                    <span className={`pill ${f.status}`}>{f.status}</span>
                  </td>
                  <td style={{ fontSize: "12px", color: f.status === "active" ? "var(--text-main)" : "var(--text-muted)" }}>
                    {f.detail || "Operational"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="empty">No capabilities match the selected filter.</div>
        )}
      </div>

      {/* Legend & Guidance */}
      <div className="card" style={{ marginTop: "18px", background: "rgba(0,0,0,0.15)" }}>
        <h5 style={{ margin: "0 0 8px", color: "var(--text-muted)", fontSize: "12px" }}>
          Capability Status Guide
        </h5>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: "10px", fontSize: "11.5px" }}>
          <div>
            <span className="pill ok" style={{ marginRight: "6px" }}>active</span>
            Feature confirmed and functional by probe.
          </div>
          <div>
            <span className="pill warn" style={{ marginRight: "6px" }}>supported_not_configured</span>
            Kernel supports it, but cgroup subtree or binaries require setup.
          </div>
          <div>
            <span className="pill blocked" style={{ marginRight: "6px" }}>blocked</span>
            Permission denied by host LSM, user namespace restriction, or missing root.
          </div>
          <div>
            <span className="pill failed" style={{ marginRight: "6px" }}>unsupported</span>
            Feature absent from this kernel or OS architecture.
          </div>
        </div>
      </div>
    </>
  );
}
