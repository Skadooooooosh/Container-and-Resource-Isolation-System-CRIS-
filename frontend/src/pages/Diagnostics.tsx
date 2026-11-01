import { api } from "../services/api";
import { Err, usePoll } from "../usePoll";

export default function Diagnostics() {
  const d = usePoll(() => api("/system/capabilities?refresh=true"), null);
  return (<>
    <h2>System Diagnostics</h2><Err msg={d.error} />
    <button className="btn" onClick={d.reload}>Re-run probes</button>
    {d.loading && <div className="empty">Probing kernel…</div>}
    {d.data && <>
      <h3>Environment</h3><div className="card"><pre>{JSON.stringify(d.data.environment, null, 2)}</pre></div>
      <h3>Capabilities (each from a real probe)</h3>
      <div className="card table-wrap"><table><thead><tr><th>Feature</th><th>Status</th><th>Detail</th></tr></thead><tbody>
        {d.data.features.map((f: any) => <tr key={f.id}><td>{f.name}</td><td><span className={`pill ${f.status}`}>{f.status}</span></td><td>{f.detail}</td></tr>)}
      </tbody></table></div>
      <p style={{ color: "var(--dim)" }}>supported_not_configured = host can do it but setup is missing · blocked = permission/policy · unsupported = kernel lacks it · failed = probe error · unknown = not checked</p>
    </>}
  </>);
}
