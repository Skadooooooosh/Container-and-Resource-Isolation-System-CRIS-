import { useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, post, patch, del } from "../services/api";
import { Err, fmtBytes, usePoll } from "../usePoll";

const WORKLOAD_TYPES = [
  { id: "cpu", label: "CPU Burn (bounded iterations)" },
  { id: "memory", label: "Memory Alloc (bounded chunk)" },
  { id: "process", label: "Process Tree (fork bounded)" },
  { id: "mixed", label: "Mixed (CPU + Memory)" },
  { id: "idle", label: "Idle (sleep/hold)" },
  { id: "nsinfo", label: "Namespace Info (dump /proc/self/ns)" },
];

function ContainerDetail({ id, onClose }: { id: string; onClose: () => void }) {
  const m = usePoll(() => api(`/containers/${id}/metrics`), 1500, [id]);
  const ps = usePoll(() => api<any[]>(`/containers/${id}/processes`), 2000, [id]);
  const lg = usePoll(() => api<string>(`/containers/${id}/logs`), 2500, [id]);
  const wl = usePoll(() => api<any[]>(`/containers/${id}/workloads`), 3000, [id]);
  const cnt = usePoll(() => api(`/containers/${id}`), 2000, [id]);

  const [patchLim, setPatchLim] = useState({ cpu: "", mem: "", pids: "" });
  const [patchErr, setPatchErr] = useState<string | null>(null);
  const [patchOk, setPatchOk] = useState(false);

  const samples = (m.data?.samples ?? []).map((x: any) => ({
    t: new Date(x.ts * 1000).toLocaleTimeString(),
    cpu: x.cpu_percent,
    mem: x.mem_bytes != null ? +(x.mem_bytes / 1048576).toFixed(1) : null,
  }));

  const cg = m.data?.cgroup;
  const c = cnt.data;

  const handleUpdateLimits = async () => {
    try {
      setPatchErr(null);
      setPatchOk(false);
      await patch(`/containers/${id}/limits`, {
        cpu_quota_percent: patchLim.cpu ? +patchLim.cpu : null,
        memory_mb: patchLim.mem ? +patchLim.mem : null,
        pids_max: patchLim.pids ? +patchLim.pids : null,
      });
      setPatchOk(true);
      cnt.reload();
      m.reload();
    } catch (e: any) {
      setPatchErr(e.message ?? String(e));
    }
  };

  return (
    <div className="card" style={{ marginTop: "24px", border: "1px solid var(--accent)" }}>
      <div className="card-header">
        <div>
          <h3 style={{ margin: 0, textTransform: "none", fontSize: "15px", color: "var(--text-bright)" }}>
            Container Inspector · <span className="mono" style={{ color: "var(--accent)" }}>{id}</span>
          </h3>
          <span style={{ fontSize: "11px", color: "var(--text-dim)" }}>
            Name: {c?.name} · State: <span className={`pill ${c?.state}`}>{c?.state}</span>
          </span>
        </div>
        <div style={{ display: "flex", gap: "8px" }}>
          <a className="btn sm" href={`/api/containers/${id}/metrics.csv`} download>
            Export CSV
          </a>
          <button className="btn sm" onClick={onClose}>
            Close Inspector
          </button>
        </div>
      </div>

      <Err msg={patchErr ?? m.error} />
      {patchOk && <div className="alert" style={{ background: "var(--ok-bg)", color: "var(--ok)" }}>Limits updated successfully.</div>}

      {/* cgroup controller telemetry summary */}
      <div className="metrics-grid" style={{ marginBottom: "16px" }}>
        <div className="metric-card">
          <span className="metric-label">Memory Current</span>
          <span className="metric-value">{fmtBytes(cg?.memory_current)}</span>
          <span className="metric-sub">Peak: {fmtBytes(cg?.memory_peak)}</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">CPU Throttled</span>
          <span className="metric-value">{cg?.nr_throttled ?? 0}</span>
          <span className="metric-sub">{cg?.throttled_usec ? `${cg.throttled_usec} µs` : "0 µs"}</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">OOM Events</span>
          <span className="metric-value" style={{ color: (cg?.mem_events?.oom_kill ?? 0) > 0 ? "var(--bad)" : "inherit" }}>
            {cg?.mem_events?.oom_kill ?? 0}
          </span>
          <span className="metric-sub">Kernel cgroup memory.events</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">Current PIDs</span>
          <span className="metric-value">{cg?.pids_current ?? "—"}</span>
          <span className="metric-sub">Inside cgroup.procs</span>
        </div>
      </div>

      {/* Real-time telemetry chart */}
      <div className="card" style={{ background: "var(--bg-input)", marginBottom: "16px" }}>
        <div className="card-header">
          <h4 className="card-title">Telemetry Stream ({samples.length ? `${samples.length} samples` : "idle"})</h4>
          <span style={{ fontSize: "11px", color: "var(--text-dim)" }}>
            {cg ? "Source: cgroup v2 accounting" : "Source: /proc RSS fallback"}
          </span>
        </div>
        {samples.length ? (
          <div style={{ height: 190 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={samples}>
                <CartesianGrid stroke="var(--border-card)" strokeDasharray="3 3" />
                <XAxis dataKey="t" stroke="var(--text-dim)" fontSize={11} />
                <YAxis yAxisId="cpu" stroke="var(--accent)" fontSize={11} unit="%" />
                <YAxis yAxisId="mem" orientation="right" stroke="var(--warn)" fontSize={11} unit=" MiB" />
                <Tooltip
                  contentStyle={{
                    background: "var(--bg-card)",
                    border: "1px solid var(--border-card)",
                    borderRadius: "6px",
                    fontSize: "12px",
                  }}
                />
                <Line
                  yAxisId="cpu"
                  dataKey="cpu"
                  name="CPU %"
                  stroke="var(--accent)"
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                />
                <Line
                  yAxisId="mem"
                  dataKey="mem"
                  name="Memory (MiB)"
                  stroke="var(--warn)"
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="empty">No telemetry samples yet. Start a container workload to collect metrics.</div>
        )}
      </div>

      {/* Adjust Resource Limits (if container not actively running) */}
      {c?.state !== "RUNNING" && c?.state !== "STARTING" && (
        <div className="card" style={{ background: "rgba(0,0,0,0.15)", marginBottom: "16px" }}>
          <h4 className="card-title" style={{ marginBottom: "8px" }}>Configure Resource Limits</h4>
          <div className="form-row">
            <div className="form-group">
              <label>CPU Quota %</label>
              <input
                size={8}
                placeholder={c?.limits?.cpu_quota_percent ?? "none"}
                value={patchLim.cpu}
                onChange={(e) => setPatchLim({ ...patchLim, cpu: e.target.value })}
              />
            </div>
            <div className="form-group">
              <label>Memory (MiB)</label>
              <input
                size={8}
                placeholder={c?.limits?.memory_mb ?? "none"}
                value={patchLim.mem}
                onChange={(e) => setPatchLim({ ...patchLim, mem: e.target.value })}
              />
            </div>
            <div className="form-group">
              <label>pids.max</label>
              <input
                size={8}
                placeholder={c?.limits?.pids_max ?? "none"}
                value={patchLim.pids}
                onChange={(e) => setPatchLim({ ...patchLim, pids: e.target.value })}
              />
            </div>
            <button className="btn primary sm" onClick={handleUpdateLimits}>
              Apply Limits
            </button>
          </div>
        </div>
      )}

      {/* Live Processes */}
      <h3>Live Processes in Container</h3>
      <div className="table-wrap" style={{ marginBottom: "16px" }}>
        {ps.data?.length ? (
          <table>
            <thead>
              <tr>
                <th>Host PID</th>
                <th>Container PID</th>
                <th>PPID</th>
                <th>Executable</th>
                <th>State</th>
                <th>RSS</th>
                <th>Elapsed</th>
              </tr>
            </thead>
            <tbody>
              {ps.data.map((p) => (
                <tr key={p.pid}>
                  <td className="mono">{p.host_pid}</td>
                  <td className="mono" style={{ color: "var(--accent)" }}>{p.container_pid}</td>
                  <td className="mono">{p.ppid}</td>
                  <td className="mono">{p.name}</td>
                  <td><span className="pill ok">{p.state}</span></td>
                  <td>{fmtBytes((p.rss_kb ?? 0) * 1024)}</td>
                  <td>{p.elapsed_s}s</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="empty">No live processes running in this container.</div>
        )}
      </div>

      {/* Workload Execution History */}
      <h3>Workload Execution History</h3>
      <div className="table-wrap" style={{ marginBottom: "16px" }}>
        {wl.data?.length ? (
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Type</th>
                <th>Termination Reason</th>
                <th>Exit Code</th>
                <th>Duration</th>
                <th>CPU Time</th>
                <th>Throttled</th>
                <th>Peak Mem</th>
                <th>OOM</th>
              </tr>
            </thead>
            <tbody>
              {wl.data.map((w) => (
                <tr key={w.id}>
                  <td className="mono">#{w.id}</td>
                  <td><span className="pill info">{w.type}</span></td>
                  <td>
                    <span className={`pill ${w.termination_reason === "completed" ? "ok" : "warn"}`}>
                      {w.termination_reason ?? "running"}
                    </span>
                  </td>
                  <td className="mono">{w.exit_code ?? "—"}</td>
                  <td>{w.duration_s ? `${w.duration_s}s` : "—"}</td>
                  <td>{w.cpu_usec != null ? `${w.cpu_usec} µs` : "n/a"}</td>
                  <td>{w.nr_throttled != null ? `${w.nr_throttled} periods` : "n/a"}</td>
                  <td>{fmtBytes(w.peak_memory_bytes)}</td>
                  <td>{w.oom_kills ?? 0}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="empty">No workloads executed yet.</div>
        )}
      </div>

      {/* Console Logs */}
      <h3>Container Output & Logs</h3>
      <pre>{lg.data || "(No log output recorded for this container)"}</pre>
    </div>
  );
}

export default function Containers() {
  const list = usePoll(() => api<any[]>("/containers"), 2000);
  const [err, setErr] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Search & Filter State
  const [search, setSearch] = useState("");
  const [stateFilter, setStateFilter] = useState("ALL");

  // Create Form State
  const [form, setForm] = useState({
    name: "worker-demo",
    cpu: "",
    mem: "",
    pids: "",
    workload: "cpu",
    seconds: 10,
  });

  const [startingId, setStartingId] = useState<string | null>(null);

  const act = async (fn: () => Promise<unknown>) => {
    try {
      setErr(null);
      await fn();
      list.reload();
    } catch (e: any) {
      setErr(e.message ?? String(e));
    }
  };

  const handleCreate = () =>
    act(() =>
      post("/containers", {
        name: form.name.trim(),
        limits: {
          cpu_quota_percent: form.cpu ? +form.cpu : null,
          memory_mb: form.mem ? +form.mem : null,
          pids_max: form.pids ? +form.pids : null,
        },
      })
    );

  const handleStart = (cid: string) => {
    setStartingId(cid);
    act(async () => {
      try {
        await post(`/containers/${cid}/start`, {
          type: form.workload,
          seconds: form.seconds,
        });
      } finally {
        setStartingId(null);
      }
    });
  };

  const handleStop = (cid: string) => act(() => post(`/containers/${cid}/stop`));

  const handleDelete = (c: any) => {
    if (window.confirm(`Are you sure you want to permanently remove container '${c.name}' (${c.id})?`)) {
      act(async () => {
        await del(`/containers/${c.id}`);
        if (selectedId === c.id) setSelectedId(null);
      });
    }
  };

  const filtered = (list.data ?? []).filter((c) => {
    const matchSearch =
      c.name.toLowerCase().includes(search.toLowerCase()) ||
      c.id.toLowerCase().includes(search.toLowerCase());
    const matchState = stateFilter === "ALL" || c.state === stateFilter;
    return matchSearch && matchState;
  });

  return (
    <>
      <div className="card-header">
        <h2>Container Management</h2>
        <button className="btn sm" onClick={() => list.reload()}>
          Refresh
        </button>
      </div>

      <Err msg={err ?? list.error} onDismiss={() => setErr(null)} />

      {/* Creation Interface */}
      <div className="card">
        <h4 className="card-title" style={{ marginBottom: "12px" }}>
          Launch New Container
        </h4>
        <div className="form-row">
          <div className="form-group">
            <label>Container Name</label>
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="e.g. worker-node-1"
            />
          </div>
          <div className="form-group">
            <label>CPU Quota %</label>
            <input
              size={6}
              placeholder="e.g. 50"
              value={form.cpu}
              onChange={(e) => setForm({ ...form, cpu: e.target.value })}
            />
          </div>
          <div className="form-group">
            <label>Memory (MiB)</label>
            <input
              size={6}
              placeholder="e.g. 128"
              value={form.mem}
              onChange={(e) => setForm({ ...form, mem: e.target.value })}
            />
          </div>
          <div className="form-group">
            <label>pids.max</label>
            <input
              size={6}
              placeholder="e.g. 32"
              value={form.pids}
              onChange={(e) => setForm({ ...form, pids: e.target.value })}
            />
          </div>
          <button className="btn primary" onClick={handleCreate} disabled={!form.name.trim()}>
            Create Container
          </button>
        </div>

        <div style={{ marginTop: "12px", display: "flex", gap: "16px", alignItems: "center" }}>
          <div className="form-group">
            <label>Default Workload for Launch</label>
            <select
              value={form.workload}
              onChange={(e) => setForm({ ...form, workload: e.target.value })}
            >
              {WORKLOAD_TYPES.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.label}
                </option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label>Hold Duration (s)</label>
            <input
              type="number"
              min={1}
              max={120}
              style={{ width: "80px" }}
              value={form.seconds}
              onChange={(e) => setForm({ ...form, seconds: +e.target.value })}
            />
          </div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
        <div style={{ display: "flex", gap: "8px" }}>
          {["ALL", "RUNNING", "STOPPED", "CREATED", "FAILED"].map((st) => (
            <button
              key={st}
              className={`btn sm ${stateFilter === st ? "primary" : ""}`}
              onClick={() => setStateFilter(st)}
            >
              {st}
            </button>
          ))}
        </div>
        <div>
          <input
            placeholder="Search by ID or name…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ width: "220px" }}
          />
        </div>
      </div>

      {/* Container Table */}
      <div className="table-wrap">
        {filtered.length ? (
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Name</th>
                <th>State</th>
                <th>Configured Limits</th>
                <th>Effective Kernel Limits</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((c) => {
                const canStart = ["CREATED", "STOPPED", "FAILED"].includes(c.state);
                const canStop = c.state === "RUNNING";
                const canDelete = ["CREATED", "STOPPED", "FAILED"].includes(c.state);
                const isSelected = selectedId === c.id;

                return (
                  <tr key={c.id} style={{ background: isSelected ? "rgba(56, 189, 248, 0.05)" : undefined }}>
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
                        onClick={() => setSelectedId(isSelected ? null : c.id)}
                      >
                        {c.id}
                      </button>
                    </td>
                    <td style={{ fontWeight: 600 }}>{c.name}</td>
                    <td>
                      <span className={`pill ${c.state}`}>{c.state}</span>
                    </td>
                    <td className="mono" style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                      {c.limits?.cpu_quota_percent ? `cpu:${c.limits.cpu_quota_percent}% ` : ""}
                      {c.limits?.memory_mb ? `mem:${c.limits.memory_mb}M ` : ""}
                      {c.limits?.pids_max ? `pids:${c.limits.pids_max}` : ""}
                      {!c.limits?.cpu_quota_percent && !c.limits?.memory_mb && !c.limits?.pids_max ? "unconstrained" : ""}
                    </td>
                    <td className="mono" style={{ fontSize: "11px" }}>
                      {c.effective_limits ? (
                        <span>
                          {c.effective_limits.cpu_quota_percent != null
                            ? `cpu ${c.effective_limits.cpu_quota_percent}% · `
                            : "cpu max · "}
                          {c.effective_limits.memory_mb != null
                            ? `mem ${c.effective_limits.memory_mb}M · `
                            : "mem max · "}
                          {c.effective_limits.pids_max != null
                            ? `pids ${c.effective_limits.pids_max}`
                            : "pids max"}
                        </span>
                      ) : (
                        <span style={{ color: "var(--text-dim)" }}>no cgroup</span>
                      )}
                    </td>
                    <td>
                      <div style={{ display: "flex", gap: "6px" }}>
                        <button
                          className="btn sm primary"
                          disabled={!canStart || startingId === c.id}
                          onClick={() => handleStart(c.id)}
                        >
                          {startingId === c.id ? "Starting…" : "Start"}
                        </button>
                        <button
                          className="btn sm"
                          disabled={!canStop}
                          onClick={() => handleStop(c.id)}
                        >
                          Stop
                        </button>
                        <button
                          className="btn sm"
                          onClick={() => setSelectedId(isSelected ? null : c.id)}
                        >
                          {isSelected ? "Hide" : "Inspect"}
                        </button>
                        <button
                          className="btn sm danger"
                          disabled={!canDelete}
                          onClick={() => handleDelete(c)}
                        >
                          Remove
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : (
          <div className="empty">
            {list.loading ? "Loading containers…" : "No containers found matching criteria."}
          </div>
        )}
      </div>

      {/* Selected Container Inspector Drawer */}
      {selectedId && <ContainerDetail id={selectedId} onClose={() => setSelectedId(null)} />}
    </>
  );
}
