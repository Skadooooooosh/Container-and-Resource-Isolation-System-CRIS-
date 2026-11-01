import { useState } from "react";
import { api } from "../services/api";
import { Err, usePoll } from "../usePoll";

export default function Logs() {
  const [q, setQ] = useState("");
  const ev = usePoll(() => api<any[]>(`/events?limit=200${q ? "&q=" + encodeURIComponent(q) : ""}`), 3000, [q]);
  return (<><h2>Logs & Events</h2><Err msg={ev.error} />
    <div className="row"><label>Search<input value={q} onChange={(e) => setQ(e.target.value)} placeholder="type or detail text" /></label></div>
    <div className="card table-wrap">{ev.data?.length ? <table><thead><tr><th>Time</th><th>Container</th><th>Type</th><th>Outcome</th><th>Detail</th></tr></thead><tbody>
      {ev.data.map((e) => <tr key={e.id}><td>{new Date(e.ts * 1000).toLocaleString()}</td><td>{e.container_id ?? "—"}</td><td>{e.type}</td><td>{e.outcome}</td><td><code>{e.detail}</code></td></tr>)}</tbody></table> : <div className="empty">No matching events.</div>}</div></>);
}
