import { useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, post } from "../services/api";
import { Err, usePoll } from "../usePoll";

export default function Experiments() {
  const defs = usePoll(() => api<any[]>("/experiments/definitions"), null);
  const list = usePoll(() => api<any[]>("/experiments"), 2000);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [runCounts, setRunCounts] = useState<Record<string, number>>({});
  const [runningKey, setRunningKey] = useState<string | null>(null);

  const cur = usePoll(
    () => (selectedId ? api(`/experiments/${selectedId}`) : Promise.resolve(null)),
    1500,
    [selectedId]
  );

  const handleRun = async (key: string, defaultRuns: number) => {
    try {
      setErr(null);
      setRunningKey(key);
      const runs = runCounts[key] || defaultRuns;
      const res = await post("/experiments", { key, runs });
      setSelectedId(res.id);
      list.reload();
    } catch (e: any) {
      setErr(e.message ?? String(e));
    } finally {
      setRunningKey(null);
    }
  };

  const x = cur.data;
  const res = x?.results;

  // Prepare comparison chart data from summary if present
  const chartData = res?.summary
    ? Object.entries<any>(res.summary).map(([k, v]) => ({
        name: k,
        wallSec: v.wall_sec ? v.wall_sec.mean : 0,
        throttledMs: v.throttled_usec ? +(v.throttled_usec.mean / 1000).toFixed(1) : 0,
        peakMemMiB: v.peak_memory_bytes ? +(v.peak_memory_bytes.mean / 1048576).toFixed(1) : 0,
      }))
    : [];

  return (
    <>
      <div className="card-header">
        <h2>
          <span>Experimentation Laboratory</span>
          <span className="platform-tag" style={{ color: "var(--ok)", borderColor: "var(--ok)" }}>
            Real Kernel Measurements Only
          </span>
        </h2>
        <button className="btn sm" onClick={() => list.reload()}>
          Refresh History
        </button>
      </div>

      <p style={{ color: "var(--text-muted)", marginTop: "-8px", marginBottom: "20px" }}>
        Reproducible OS isolation experiments. Each run executes real workloads under strict cgroups v2
        enforcement, reads kernel counters, and calculates mean and standard deviations. No fake data is produced.
      </p>

      <Err msg={err ?? defs.error} onDismiss={() => setErr(null)} />

      {/* Available Experiments Grid */}
      <h3>Available Isolation Benchmarks</h3>
      <div className="metrics-grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))" }}>
        {(defs.data ?? []).map((d) => {
          const currentRuns = runCounts[d.key] || d.default_runs;
          const isRunningThis = runningKey === d.key;

          return (
            <div className="card" key={d.key} style={{ display: "flex", flexDirection: "column" }}>
              <div style={{ flex: 1 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "8px" }}>
                  <h4 className="card-title" style={{ fontSize: "14px" }}>{d.title}</h4>
                  <span className="mono" style={{ fontSize: "10px", color: "var(--text-dim)" }}>{d.key}</span>
                </div>
                <p style={{ color: "var(--text-muted)", fontSize: "12px", lineHeight: 1.45, marginBottom: "8px" }}>
                  {d.hypothesis}
                </p>
                <div style={{ fontSize: "11px", color: "var(--text-dim)", marginBottom: "14px" }}>
                  <strong>Objective:</strong> {d.objective}
                </div>
                <div style={{ fontSize: "10.5px", color: "var(--warn)", background: "var(--warn-bg)", padding: "6px 8px", borderRadius: "4px", marginBottom: "14px" }}>
                  ⚠ {d.limitations}
                </div>
              </div>

              <div style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: "12px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                  <label style={{ fontSize: "11px", color: "var(--text-muted)" }}>Runs/cfg:</label>
                  <input
                    type="number"
                    min={1}
                    max={10}
                    value={currentRuns}
                    onChange={(e) =>
                      setRunCounts({ ...runCounts, [d.key]: Math.max(1, Math.min(10, +e.target.value)) })
                    }
                    style={{ width: "50px", padding: "4px 6px" }}
                  />
                </div>
                <button
                  className="btn primary sm"
                  disabled={isRunningThis}
                  onClick={() => handleRun(d.key, d.default_runs)}
                >
                  {isRunningThis ? "Launching…" : `Execute Benchmark (${currentRuns} runs)`}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Selected Experiment Inspector */}
      {x && (
        <div className="card" style={{ marginTop: "24px", border: "1px solid var(--accent)" }}>
          <div className="card-header">
            <div>
              <h3 style={{ margin: 0, textTransform: "none", fontSize: "15px", color: "var(--text-bright)" }}>
                Benchmark Run · <span className="mono" style={{ color: "var(--accent)" }}>{x.id}</span> ({x.key})
              </h3>
              <span style={{ fontSize: "11px", color: "var(--text-dim)" }}>
                Status: <span className={`pill ${x.status}`}>{x.status}</span> · Progress: {x.progress || "0"}
              </span>
            </div>
            <div style={{ display: "flex", gap: "8px" }}>
              {x.status === "completed" && (
                <a className="btn sm primary" href={`/api/experiments/${x.id}/results.json`} download>
                  Download Raw JSON
                </a>
              )}
              <button className="btn sm" onClick={() => setSelectedId(null)}>
                Close
              </button>
            </div>
          </div>

          {res?.error && <Err msg={res.error} />}

          {/* Statistical Summary Table */}
          {res?.summary && (
            <>
              <h4 className="card-title" style={{ fontSize: "13px", marginTop: "14px", marginBottom: "8px" }}>
                Statistical Measurement Summary
              </h4>
              <div className="table-wrap" style={{ marginBottom: "18px" }}>
                <table>
                  <thead>
                    <tr>
                      <th>Configuration</th>
                      <th>Runs (n)</th>
                      <th>Wall-Clock Time (mean ± stdev)</th>
                      <th>CPU Throttled (mean)</th>
                      <th>Peak Memory (mean)</th>
                      <th>Termination Outlines</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries<any>(res.summary).map(([k, v]) => (
                      <tr key={k}>
                        <td style={{ fontWeight: 600 }}>{k}</td>
                        <td className="mono">{v.runs}</td>
                        <td className="mono" style={{ color: "var(--accent)" }}>
                          {v.wall_sec ? `${v.wall_sec.mean}s ± ${v.wall_sec.stdev}s` : "—"}
                        </td>
                        <td className="mono">{v.throttled_usec ? `${(v.throttled_usec.mean / 1000).toFixed(1)} ms` : "0 ms"}</td>
                        <td className="mono">{v.peak_memory_bytes ? `${(v.peak_memory_bytes.mean / 1048576).toFixed(1)} MiB` : "n/a"}</td>
                        <td>
                          <span className="pill ok">{v.reasons.join(", ")}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}

          {/* Comparison Bar Chart */}
          {chartData.length > 0 && (
            <div className="card" style={{ background: "var(--bg-input)", marginBottom: "18px" }}>
              <h4 className="card-title" style={{ fontSize: "12px", marginBottom: "12px" }}>
                Configuration Comparison (Mean Wall Time & Throttling)
              </h4>
              <div style={{ height: 210 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData}>
                    <CartesianGrid stroke="var(--border-card)" strokeDasharray="3 3" />
                    <XAxis dataKey="name" stroke="var(--text-dim)" fontSize={11} />
                    <YAxis stroke="var(--text-dim)" fontSize={11} unit="s" />
                    <Tooltip
                      contentStyle={{
                        background: "var(--bg-card)",
                        border: "1px solid var(--border-card)",
                        borderRadius: "6px",
                        fontSize: "12px",
                      }}
                    />
                    <Bar dataKey="wallSec" name="Mean Wall Clock (seconds)" fill="#38bdf8" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="throttledMs" name="Mean Throttled (ms)" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Scientific Interpretation */}
          {res?.interpretation && (
            <div className="card" style={{ background: "rgba(56, 189, 248, 0.04)", border: "1px solid rgba(56, 189, 248, 0.2)" }}>
              <h4 className="card-title" style={{ fontSize: "13px", color: "var(--accent)", marginBottom: "8px" }}>
                Kernel Accounting Analysis
              </h4>
              {res.interpretation.map((text: string, i: number) => (
                <div key={i} style={{ display: "flex", gap: "8px", marginBottom: "6px", fontSize: "12.5px" }}>
                  <span style={{ color: "var(--accent)" }}>✓</span>
                  <span>{text}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Experiment Run History Table */}
      <h3>Execution History</h3>
      <div className="table-wrap">
        {list.data?.length ? (
          <table>
            <thead>
              <tr>
                <th>Experiment ID</th>
                <th>Benchmark Key</th>
                <th>Status</th>
                <th>Progress</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {list.data.map((e) => (
                <tr key={e.id}>
                  <td>
                    <button
                      className="btn sm"
                      style={{
                        fontFamily: "var(--font-mono)",
                        color: "var(--accent)",
                        border: "none",
                        background: "none",
                        padding: 0,
                        cursor: "pointer",
                      }}
                      onClick={() => setSelectedId(e.id)}
                    >
                      {e.id}
                    </button>
                  </td>
                  <td style={{ fontWeight: 600 }}>{e.key}</td>
                  <td>
                    <span className={`pill ${e.status}`}>{e.status}</span>
                  </td>
                  <td className="mono">{e.progress}</td>
                  <td>
                    <button className="btn sm" onClick={() => setSelectedId(e.id)}>
                      View Results
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="empty">No experiments executed yet. Launch a benchmark above.</div>
        )}
      </div>
    </>
  );
}
