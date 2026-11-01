import { api } from "../services/api";
import { Err, fmtBytes, usePoll } from "../usePoll";

export default function Overview() {
  const m = usePoll(() => api("/system/metrics"), 2000);
  const ev = usePoll(() => api<any[]>("/events?limit=8"), 3000);
  const h = m.data?.host, c = m.data?.containers;
  const K = ({ k, v, s }: { k: string; v: any; s: string }) => <div className="card kv"><div className="k">{k}</div><div className="v">{v ?? "—"}</div><div className="s">{s}</div></div>;
  return (<>
    <h2>Overview</h2><Err msg={m.error} />
    <div className="grid">
      <K k="Managed containers" v={c?.total} s="SQLite containers table" />
      <K k="Running" v={c?.running} s="state=RUNNING (pid verified on start/reconcile)" />
      <K k="Stopped / failed" v={c?.stopped_or_failed} s="state in STOPPED, FAILED" />
      <K k="Host CPU" v={h?.cpu_percent != null ? h.cpu_percent + " %" : null} s={`/proc/stat delta, ${h?.cpus ?? "?"} CPUs`} />
      <K k="Host memory" v={h ? `${h.mem_percent} %` : null} s={h ? `${fmtBytes(h.mem_used_bytes)} of ${fmtBytes(h.mem_total_bytes)} (/proc/meminfo)` : ""} />
    </div>
    <h3>Recent lifecycle events</h3>
    <div className="card table-wrap">{ev.data?.length ? <table><thead><tr><th>Time</th><th>Container</th><th>Type</th><th>Outcome</th></tr></thead><tbody>
      {ev.data.map((e) => <tr key={e.id}><td>{new Date(e.ts * 1000).toLocaleTimeString()}</td><td>{e.container_id ?? "—"}</td><td>{e.type}</td><td>{e.outcome}</td></tr>)}
    </tbody></table> : <div className="empty">No events yet. Create a container to begin.</div>}</div>
  </>);
}
