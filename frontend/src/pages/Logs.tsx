import { useState } from "react";
import { api } from "../services/api";
import { Err, usePoll } from "../usePoll";

export default function Logs() {
  const [query, setQuery] = useState("");
  const [outcomeFilter, setOutcomeFilter] = useState("ALL");
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const ev = usePoll(
    () => api<any[]>(`/events?limit=250${query ? "&q=" + encodeURIComponent(query) : ""}`),
    autoRefresh ? 3000 : null,
    [query],
    true
  );

  const filtered = (ev.data ?? []).filter((e) => {
    if (outcomeFilter === "ALL") return true;
    if (outcomeFilter === "OK") return e.outcome === "ok";
    if (outcomeFilter === "FAILED") return e.outcome === "failed";
    if (outcomeFilter === "OTHER") return e.outcome !== "ok" && e.outcome !== "failed";
    return true;
  });

  return (
    <>
      <div className="card-header">
        <h2>System Logs & Audit Trail</h2>
        <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
          <label style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px", cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
            />
            Live Stream (3s)
          </label>
          <button className="btn sm" onClick={ev.reload}>
            Refresh
          </button>
        </div>
      </div>

      <p style={{ color: "var(--text-muted)", marginTop: "-8px", marginBottom: "18px" }}>
        Append-only SQLite audit log recording every container transition, cgroup limit application, supervisor
        exit, and host reconciliation event.
      </p>

      <Err msg={ev.error} />

      {/* Controls Bar: Search & Severity Filter */}
      <div className="card" style={{ padding: "12px 16px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "12px" }}>
          <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
            <span style={{ fontSize: "11px", fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase" }}>
              Filter Outcome:
            </span>
            {["ALL", "OK", "FAILED", "OTHER"].map((f) => (
              <button
                key={f}
                className={`btn sm ${outcomeFilter === f ? "primary" : ""}`}
                onClick={() => setOutcomeFilter(f)}
              >
                {f}
              </button>
            ))}
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <label style={{ fontSize: "11px", fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase" }}>
              Search:
            </label>
            <input
              placeholder="Search type, cid, or detail…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              style={{ width: "240px" }}
            />
            {query && (
              <button className="btn sm" onClick={() => setQuery("")}>
                Clear
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Events Table */}
      <div className="table-wrap">
        {filtered.length ? (
          <table>
            <thead>
              <tr>
                <th style={{ width: "80px" }}>ID</th>
                <th style={{ width: "160px" }}>Timestamp</th>
                <th style={{ width: "120px" }}>Container</th>
                <th style={{ width: "130px" }}>Event Type</th>
                <th style={{ width: "100px" }}>Outcome</th>
                <th>Event Metadata & Parameters</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((e) => {
                const isExpanded = expandedId === e.id;
                let parsedDetail: any = null;
                try {
                  parsedDetail = JSON.parse(e.detail);
                } catch {
                  parsedDetail = e.detail;
                }

                return (
                  <tr
                    key={e.id}
                    style={{
                      background: isExpanded ? "rgba(56, 189, 248, 0.05)" : undefined,
                      cursor: "pointer",
                    }}
                    onClick={() => setExpandedId(isExpanded ? null : e.id)}
                  >
                    <td className="mono" style={{ fontSize: "11px", color: "var(--text-dim)" }}>
                      #{e.id}
                    </td>
                    <td className="mono" style={{ fontSize: "11.5px", color: "var(--text-muted)" }}>
                      {new Date(e.ts * 1000).toLocaleString()}
                    </td>
                    <td>
                      {e.container_id ? (
                        <span className="mono" style={{ color: "var(--accent)", fontSize: "11px" }}>
                          {e.container_id}
                        </span>
                      ) : (
                        <span style={{ color: "var(--text-dim)" }}>host</span>
                      )}
                    </td>
                    <td>
                      <span className="mono" style={{ fontWeight: 600 }}>{e.type}</span>
                    </td>
                    <td>
                      <span
                        className={`pill ${
                          e.outcome === "ok" ? "ok" : e.outcome === "failed" ? "bad" : "warn"
                        }`}
                      >
                        {e.outcome}
                      </span>
                    </td>
                    <td>
                      <div className="mono" style={{ fontSize: "11.5px", color: "var(--text-main)" }}>
                        {typeof parsedDetail === "string" ? parsedDetail : JSON.stringify(parsedDetail)}
                      </div>
                      {isExpanded && (
                        <pre style={{ marginTop: "8px", fontSize: "11px" }}>
                          {JSON.stringify(parsedDetail, null, 2)}
                        </pre>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : (
          <div className="empty">
            {ev.loading ? "Loading audit events…" : "No events matched the search or filter query."}
          </div>
        )}
      </div>
    </>
  );
}
