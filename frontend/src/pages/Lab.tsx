import { useState } from "react";
import { api, post } from "../services/api";
import { Err } from "../usePoll";

const SAMPLES: Record<string, { path: string; body: any; label: string }> = {
  scheduling: { label: "CPU scheduling (algorithms: fcfs, sjf, srtf, priority, priority_preemptive, rr, mlfq)", path: "/lab/scheduling",
    body: { algorithm: "rr", quantum: 2, processes: [{ pid: "P1", arrival: 0, burst: 5 }, { pid: "P2", arrival: 1, burst: 3 }, { pid: "P3", arrival: 2, burst: 8 }, { pid: "P4", arrival: 3, burst: 6 }] } },
  paging: { label: "Page replacement (fifo, lru, optimal)", path: "/lab/memory/replacement", body: { algorithm: "lru", frames: 3, references: [7, 0, 1, 2, 0, 3, 0, 4, 2, 3, 0, 3, 2, 1, 2, 0, 1, 7, 0, 1] } },
  translate: { label: "Address translation + TLB", path: "/lab/memory/translate", body: { addresses: [1030, 1030, 5000], page_size: 1024, tlb_size: 2, page_table: { "1": 7, "4": 2 } } },
  banker: { label: "Banker's algorithm (add request_pid + request for a request check)", path: "/lab/deadlock/banker",
    body: { available: [3, 3, 2], maximum: [[7, 5, 3], [3, 2, 2], [9, 0, 2], [2, 2, 2], [4, 3, 3]], allocation: [[0, 1, 0], [2, 0, 0], [3, 0, 2], [2, 1, 1], [0, 0, 2]] } },
  disk: { label: "Disk scheduling (fcfs, sstf, scan, cscan, look, clook)", path: "/lab/disk-scheduling", body: { algorithm: "look", head: 53, disk_size: 200, direction: "down", requests: [98, 183, 37, 122, 14, 124, 65, 67] } },
};

export default function Lab() {
  const [k, setK] = useState("scheduling");
  const [text, setText] = useState(JSON.stringify(SAMPLES.scheduling.body, null, 2));
  const [out, setOut] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const pick = (v: string) => { setK(v); setText(JSON.stringify(SAMPLES[v].body, null, 2)); setOut(null); setErr(null); };
  const run = async () => { try { setErr(null); setOut(await post(SAMPLES[k].path, JSON.parse(text))); } catch (e: any) { setErr(e.message); setOut(null); } };
  const quick = async (p: string) => { try { setErr(null); setOut(await api(p)); } catch (e: any) { setErr(e.message); } };
  const total = out?.gantt ? out.gantt[out.gantt.length - 1].end : 1;
  return (<>
    <h2>OS Laboratory <span className="sim">simulations — not kernel behaviour</span></h2>
    <div className="card">
      <div className="row"><label>Module<select value={k} onChange={(e) => pick(e.target.value)}>{Object.entries(SAMPLES).map(([v, s]) => <option key={v} value={v}>{s.label}</option>)}</select></label>
        <button className="btn primary" onClick={run}>Simulate</button><button className="btn" onClick={() => pick(k)}>Reset</button></div>
      <textarea aria-label="Input JSON" value={text} onChange={(e) => setText(e.target.value)} />
    </div>
    <div className="card"><div className="row"><b>Synchronization:</b>
      <button className="btn" onClick={() => quick("/lab/synchronization/race?schedule=interleaved")}>Race (interleaved)</button>
      <button className="btn" onClick={() => quick("/lab/synchronization/race?schedule=serial")}>Race (serial)</button>
      <button className="btn" onClick={() => quick("/lab/synchronization/producer-consumer")}>Producer–consumer (real threads)</button>
      <button className="btn" onClick={() => quick("/lab/synchronization/dining-philosophers?strategy=naive")}>Philosophers (naive)</button>
      <button className="btn" onClick={() => quick("/lab/synchronization/dining-philosophers?strategy=ordered")}>Philosophers (ordered)</button></div></div>
    <Err msg={err} />
    {out?.gantt && <div className="card"><h3>Gantt</h3><div className="gantt">{out.gantt.map((g: any, i: number) => <div key={i} style={{ width: `${((g.end - g.start) / total) * 100}%` }} title={`${g.pid} ${g.start}-${g.end}`}>{g.pid}</div>)}</div>
      <p>avg waiting {out.avg_waiting} · avg turnaround {out.avg_turnaround} · avg response {out.avg_response}</p></div>}
    {out?.table && <div className="card table-wrap"><table><thead><tr>{Object.keys(out.table[0]).map((c) => <th key={c}>{c}</th>)}</tr></thead><tbody>{out.table.map((r: any, i: number) => <tr key={i}>{Object.values(r).map((v: any, j) => <td key={j}>{String(v)}</td>)}</tr>)}</tbody></table></div>}
    {out && <div className="card"><h3>Raw result</h3><pre>{JSON.stringify(out, null, 2)}</pre></div>}
  </>);
}
