import { useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, post } from "../services/api";
import { Err, fmtBytes, usePoll } from "../usePoll";

const TYPES = ["cpu", "memory", "process", "mixed", "idle", "nsinfo"];

function Detail({ id }: { id: string }) {
  const m = usePoll(() => api(`/containers/${id}/metrics`), 1000, [id]);
  const ps = usePoll(() => api<any[]>(`/containers/${id}/processes`), 1500, [id]);
  const lg = usePoll(() => api<string>(`/containers/${id}/logs`), 2000, [id]);
  const wl = usePoll(() => api<any[]>(`/containers/${id}/workloads`), 3000, [id]);
  const s = (m.data?.samples ?? []).map((x: any) => ({ t: new Date(x.ts * 1000).toLocaleTimeString(), cpu: x.cpu_percent, mem: x.mem_bytes != null ? x.mem_bytes / 1048576 : null }));
  const cg = m.data?.cgroup;
  return (<div className="card">
    <h3>Detail · {id}</h3><Err msg={m.error} />
    {cg ? <p>cgroup: throttled {cg.nr_throttled} periods ({cg.throttled_usec} µs) · mem.current {fmtBytes(cg.memory_current)} · mem.peak {fmtBytes(cg.memory_peak)} · oom_kill {cg.mem_events?.oom_kill ?? 0} · pids {cg.pids_current ?? "—"}</p>
      : <p className="empty">No cgroup for this container (cgroup v2 unavailable) — charts fall back to /proc RSS sums.</p>}
    {s.length ? <div style={{ height: 200 }}><ResponsiveContainer><LineChart data={s}><CartesianGrid stroke="var(--line)" /><XAxis dataKey="t" stroke="var(--dim)" /><YAxis yAxisId="a" stroke="var(--accent)" unit="%" /><YAxis yAxisId="b" orientation="right" stroke="var(--warn)" unit=" MiB" /><Tooltip />
      <Line yAxisId="a" dataKey="cpu" name="CPU %" stroke="var(--accent)" dot={false} connectNulls={false} isAnimationActive={false} /><Line yAxisId="b" dataKey="mem" name="Memory MiB" stroke="var(--warn)" dot={false} isAnimationActive={false} /></LineChart></ResponsiveContainer></div>
      : <div className="empty">No samples yet. Start a workload.</div>}
    <a className="btn" href={`/api/containers/${id}/metrics.csv`}>Download samples (CSV)</a>
    <h3>Processes (host PID → container PID)</h3>
    <div className="table-wrap">{ps.data?.length ? <table><thead><tr><th>Host PID</th><th>Container PID</th><th>PPID</th><th>Name</th><th>State</th><th>RSS</th><th>Elapsed</th></tr></thead><tbody>
      {ps.data.map((p) => <tr key={p.pid}><td>{p.host_pid}</td><td>{p.container_pid}</td><td>{p.ppid}</td><td>{p.name}</td><td>{p.state}</td><td>{fmtBytes((p.rss_kb ?? 0) * 1024)}</td><td>{p.elapsed_s}s</td></tr>)}</tbody></table> : <div className="empty">No live processes.</div>}</div>
    <h3>Workload history</h3>
    <div className="table-wrap"><table><thead><tr><th>#</th><th>Type</th><th>Reason</th><th>Exit</th><th>Duration</th><th>CPU µs</th><th>Throttled</th><th>Peak mem</th><th>OOM</th></tr></thead><tbody>
      {(wl.data ?? []).map((w) => <tr key={w.id}><td>{w.id}</td><td>{w.type}</td><td>{w.termination_reason ?? "running"}</td><td>{w.exit_code ?? "—"}</td><td>{w.duration_s ?? "—"}</td><td>{w.cpu_usec ?? "n/a"}</td><td>{w.nr_throttled ?? "n/a"}</td><td>{fmtBytes(w.peak_memory_bytes)}</td><td>{w.oom_kills ?? "n/a"}</td></tr>)}</tbody></table></div>
    <h3>Logs</h3><pre>{lg.data || "(empty)"}</pre>
  </div>);
}

export default function Containers() {
  const list = usePoll(() => api<any[]>("/containers"), 1500);
  const [err, setErr] = useState<string | null>(null);
  const [sel, setSel] = useState<string | null>(null);
  const [f, setF] = useState({ name: "demo", cpu: "", mem: "", pids: "" });
  const [wt, setWt] = useState("cpu");
  const act = async (fn: () => Promise<unknown>) => { try { setErr(null); await fn(); } catch (e: any) { setErr(e.message); } list.reload(); };
  const create = () => act(() => post("/containers", { name: f.name, limits: { cpu_quota_percent: f.cpu ? +f.cpu : null, memory_mb: f.mem ? +f.mem : null, pids_max: f.pids ? +f.pids : null } }));
  return (<>
    <h2>Containers</h2><Err msg={err ?? list.error} />
    <div className="card"><div className="row">
      <label>Name<input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></label>
      <label>CPU quota %<input size={6} placeholder="none" value={f.cpu} onChange={(e) => setF({ ...f, cpu: e.target.value })} /></label>
      <label>Memory MiB<input size={6} placeholder="none" value={f.mem} onChange={(e) => setF({ ...f, mem: e.target.value })} /></label>
      <label>pids.max<input size={6} placeholder="none" value={f.pids} onChange={(e) => setF({ ...f, pids: e.target.value })} /></label>
      <button className="btn primary" onClick={create}>Create</button>
      <label>Workload<select value={wt} onChange={(e) => setWt(e.target.value)}>{TYPES.map((t) => <option key={t}>{t}</option>)}</select></label>
    </div></div>
    <div className="card table-wrap">{list.data?.length ? <table><thead><tr><th>ID</th><th>Name</th><th>State</th><th>Requested limits</th><th>Effective (kernel)</th><th>Actions</th></tr></thead><tbody>
      {list.data.map((c) => <tr key={c.id}><td><a href="#Containers" onClick={() => setSel(c.id)}>{c.id}</a></td><td>{c.name}</td><td><span className={`pill ${c.state}`}>{c.state}</span></td>
        <td>{JSON.stringify(c.limits)}</td><td>{c.effective_limits ? `cpu ${c.effective_limits.cpu_quota_percent ?? "max"}% · mem ${c.effective_limits.memory_mb ?? "max"} MiB · pids ${c.effective_limits.pids_max ?? "max"}` : "no cgroup"}</td>
        <td><button className="btn" disabled={!["CREATED", "STOPPED", "FAILED"].includes(c.state)} onClick={() => act(() => post(`/containers/${c.id}/start`, { type: wt, seconds: 10 }))}>Start</button>{" "}
          <button className="btn" disabled={c.state !== "RUNNING"} onClick={() => act(() => post(`/containers/${c.id}/stop`))}>Stop</button>{" "}
          <button className="btn danger" disabled={c.state === "RUNNING" || c.state === "STARTING" || c.state === "STOPPING"} onClick={() => { if (confirm(`Remove ${c.name}?`)) act(() => api(`/containers/${c.id}`, { method: "DELETE" })); }}>Remove</button></td></tr>)}
    </tbody></table> : <div className="empty">{list.loading ? "Loading…" : "No containers yet."}</div>}</div>
    {sel && <Detail id={sel} />}
  </>);
}
