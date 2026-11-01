import { useState } from "react";
import { api, post } from "../services/api";
import { Err, usePoll } from "../usePoll";

export default function Experiments() {
  const defs = usePoll(() => api<any[]>("/experiments/definitions"), null);
  const list = usePoll(() => api<any[]>("/experiments"), 2000);
  const [sel, setSel] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const cur = usePoll(() => (sel ? api(`/experiments/${sel}`) : Promise.resolve(null)), 1500, [sel]);
  const run = async (key: string) => { try { setErr(null); const r = await post("/experiments", { key }); setSel(r.id); list.reload(); } catch (e: any) { setErr(e.message); } };
  const x = cur.data, res = x?.results;
  return (<>
    <h2>Experiment Lab</h2><Err msg={err ?? defs.error} />
    <div className="grid">{(defs.data ?? []).map((d) => <div className="card" key={d.key}><b>{d.title}</b><p style={{ color: "var(--dim)" }}>{d.hypothesis}</p>
      <p style={{ fontSize: 11 }}>Limitations: {d.limitations}</p><button className="btn primary" onClick={() => run(d.key)}>Run ({d.default_runs} runs/config)</button></div>)}</div>
    <h3>History</h3><div className="card table-wrap">{list.data?.length ? <table><tbody>{list.data.map((e) => <tr key={e.id}><td><a href="#Experiment%20Lab" onClick={() => setSel(e.id)}>{e.id}</a></td><td>{e.key}</td><td><span className={`pill ${e.status}`}>{e.status}</span></td><td>{e.progress}</td></tr>)}</tbody></table> : <div className="empty">No experiments run yet.</div>}</div>
    {x && <div className="card"><h3>{x.key} · {x.status} {x.progress && `· ${x.progress}`}</h3>
      {res?.summary && <div className="table-wrap"><table><thead><tr><th>Config</th><th>n</th><th>wall s (mean±sd)</th><th>throttled µs (mean)</th><th>peak mem (mean B)</th><th>termination</th></tr></thead><tbody>
        {Object.entries<any>(res.summary).map(([k, v]) => <tr key={k}><td>{k}</td><td>{v.runs}</td><td>{v.wall_sec ? `${v.wall_sec.mean} ± ${v.wall_sec.stdev}` : "—"}</td><td>{v.throttled_usec?.mean ?? "n/a"}</td><td>{v.peak_memory_bytes?.mean ?? "n/a"}</td><td>{v.reasons.join(", ")}</td></tr>)}</tbody></table></div>}
      {res?.interpretation?.map((t: string, i: number) => <p key={i}>• {t}</p>)}
      {res?.error && <Err msg={res.error} />}
      {x.status === "completed" && <a className="btn" href={`/api/experiments/${x.id}/results.json`} download>Export raw results (JSON)</a>}
      <h3>Environment</h3><pre>{JSON.stringify(x.environment, null, 2)}</pre></div>}
  </>);
}
