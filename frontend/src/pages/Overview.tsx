import { useState, useEffect } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../services/api";
import { Err, fmtBytes, usePoll } from "../usePoll";

interface HostPoint {
  t: string;
  cpu: number | null;
  mem: number | null;
}

export default function Overview() {
  const m = usePoll(() => api("/system/metrics"), 2000);
  const ev = usePoll(() => api<any[]>("/events?limit=10"), 3000);
  const caps = usePoll(() => api("/system/capabilities"), 10000);

  const [history, setHistory] = useState<HostPoint[]>([]);

  const h = m.data?.host;
  const c = m.data?.containers;

  // Track host CPU & Memory history from real poll responses
  useEffect(() => {
    if (!h || (h.cpu_percent == null && h.mem_percent == null)) return;
    const nowStr = new Date().toLocaleTimeString();
    setHistory((prev) => {
      const next = [...prev, { t: nowStr, cpu: h.cpu_percent, mem: h.mem_percent }];
      return next.slice(-25); // retain last 25 real data points
    });
  }, [h]);

  const nsList = (caps.data?.features ?? []).filter((f: any) => f.id.startsWith("ns."));
  const activeNsCount = nsList.filter((f: any) => f.status === "active").length;

  const cgList = (caps.data?.features ?? []).filter((f: any) => f.id.startsWith("cgroup."));
  const activeCgCount = cgList.filter((f: any) => f.status === "active").length;

  return (
    <>
      <div className="card-header">
        <h2>Infrastructure Overview</h2>
        <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
          <span className="pill ok">System Online</span>
          <button className="btn sm" onClick={() => { m.reload(); ev.reload(); caps.reload(); }}>
            Refresh
          </button>
        </div>
      </div>

      <Err msg={m.error ?? ev.error} />

      <div className="metrics-grid">
        <div className="metric-card">
          <span className="metric-label">Total Containers</span>
          <span className="metric-value">{c?.total ?? 0}</span>
          <span className="metric-sub">SQLite metadata store</span>
        </div>

        <div className="metric-card">
          <span className="metric-label">Running</span>
          <span className="metric-value" style={{ color: "var(--ok)" }}>
            {c?.running ?? 0}
          </span>
          <span className="metric-sub">Verified via /proc liveness</span>
        </div>

        <div className="metric-card">
          <span className="metric-label">Stopped / Failed</span>
          <span className="metric-value" style={{ color: "var(--warn)" }}>
            {c?.stopped_or_failed ?? 0}
          </span>
          <span className="metric-sub">Inactive workload state</span>
        </div>

        <div className="metric-card">
          <span className="metric-label">Host CPU</span>
          <span
            className="metric-value"
            style={{
              fontSize: h?.cpu_percent != null ? undefined : "13px",
              color: h?.cpu_percent != null ? undefined : "var(--text-dim)",
            }}
          >
            {h?.cpu_percent != null ? `${h.cpu_percent} %` : "Unavailable on this platform"}
          </span>
          {h?.cpu_percent != null && (
            <div className="progress-bar-wrap">
              <div
                className={`progress-bar-fill ${
                  h.cpu_percent > 85 ? "bad" : h.cpu_percent > 60 ? "warn" : "ok"
                }`}
                style={{ width: `${Math.min(h.cpu_percent, 100)}%` }}
              ></div>
            </div>
          )}
          <span className="metric-sub">
            {h?.cpus ? `${h.cpus} Cores · ` : ""}
            {h?.source ?? "Hardware counters"}
          </span>
        </div>

        <div className="metric-card">
          <span className="metric-label">Host Memory</span>
          <span
            className="metric-value"
            style={{
              fontSize: h?.mem_percent != null ? undefined : "13px",
              color: h?.mem_percent != null ? undefined : "var(--text-dim)",
            }}
          >
            {h?.mem_percent != null ? `${h.mem_percent} %` : "Unavailable on this platform"}
          </span>
          {h?.mem_percent != null && (
            <div className="progress-bar-wrap">
              <div
                className={`progress-bar-fill ${
                  h.mem_percent > 85 ? "bad" : h.mem_percent > 60 ? "warn" : "ok"
                }`}
                style={{ width: `${Math.min(h.mem_percent, 100)}%` }}
              ></div>
            </div>
          )}
          <span className="metric-sub">
            {h?.mem_used_bytes != null && h?.mem_total_bytes != null
              ? `${fmtBytes(h.mem_used_bytes)} / ${fmtBytes(h.mem_total_bytes)}`
              : "Unavailable on this platform"}
          </span>
        </div>
      </div>

      {/* Host Real-Time Telemetry */}
      {history.length > 1 && (
        <div className="card">
          <div className="card-header">
            <h4 className="card-title">Real-Time Host Telemetry (Live /proc sampling)</h4>
            <span style={{ fontSize: "11px", color: "var(--text-dim)" }}>
              Polling every 2s
            </span>
          </div>
          <div style={{ height: 210 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={history}>
                <CartesianGrid stroke="var(--border-subtle)" strokeDasharray="3 3" />
                <XAxis dataKey="t" stroke="var(--text-dim)" fontSize={11} />
                <YAxis stroke="var(--text-dim)" fontSize={11} unit="%" domain={[0, 100]} />
                <Tooltip
                  contentStyle={{
                    background: "var(--bg-card)",
                    border: "1px solid var(--border-card)",
                    borderRadius: "6px",
                    fontSize: "12px",
                  }}
                />
                <Line
                  dataKey="cpu"
                  name="CPU %"
                  stroke="var(--accent)"
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                />
                <Line
                  dataKey="mem"
                  name="Memory %"
                  stroke="var(--warn)"
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Isolation Status Panels */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginBottom: "18px" }}>
        <div className="card" style={{ margin: 0 }}>
          <div className="card-header">
            <h4 className="card-title">Linux Namespaces</h4>
            <span className={`pill ${activeNsCount > 0 ? "ok" : "blocked"}`}>
              {activeNsCount} / {nsList.length || 6} Active
            </span>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
            {nsList.map((ns: any) => (
              <span key={ns.id} className={`pill ${ns.status}`} title={ns.detail}>
                {ns.name}
              </span>
            ))}
          </div>
        </div>

        <div className="card" style={{ margin: 0 }}>
          <div className="card-header">
            <h4 className="card-title">cgroups v2 Controllers</h4>
            <span className={`pill ${activeCgCount > 0 ? "ok" : "blocked"}`}>
              {activeCgCount} / {cgList.length || 4} Active
            </span>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
            {cgList.map((cg: any) => (
              <span key={cg.id} className={`pill ${cg.status}`} title={cg.detail}>
                {cg.name}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Recent Lifecycle Events Table */}
      <h3>Recent Lifecycle Events</h3>
      <div className="table-wrap">
        {ev.data?.length ? (
          <table>
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Container</th>
                <th>Event Type</th>
                <th>Outcome</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              {ev.data.map((e) => (
                <tr key={e.id}>
                  <td className="mono" style={{ fontSize: "11.5px", color: "var(--text-muted)" }}>
                    {new Date(e.ts * 1000).toLocaleTimeString()}
                  </td>
                  <td>
                    {e.container_id ? (
                      <a
                        href="#Containers"
                        className="mono"
                        style={{ color: "var(--accent)", textDecoration: "none" }}
                      >
                        {e.container_id}
                      </a>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td>
                    <span className="mono">{e.type}</span>
                  </td>
                  <td>
                    <span
                      className={`pill ${
                        e.outcome === "ok" ? "ok" : e.outcome === "failed" ? "failed" : "running"
                      }`}
                    >
                      {e.outcome}
                    </span>
                  </td>
                  <td className="mono" style={{ fontSize: "11px", color: "var(--text-dim)" }}>
                    {e.detail}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="empty">No events yet. Create and launch a container to inspect events.</div>
        )}
      </div>
    </>
  );
}
