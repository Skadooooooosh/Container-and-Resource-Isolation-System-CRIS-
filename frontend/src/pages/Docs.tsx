export default function Docs() {
  return (<><h2>Documentation & About</h2><div className="card">
    <p><b>Real</b>: containers (clone(2) namespaces), cgroup v2 limits, /proc monitoring, experiments. <b>Simulated</b>: everything in the OS Laboratory (labelled).</p>
    <p>Layers: React UI → FastAPI orchestration → C launcher (<code>cris_run</code>) → Linux kernel (namespaces, cgroups, scheduler, VM).</p>
    <p>See <code>docs/</code> in the repository for architecture, OS concepts, security, testing, demo guide and viva questions. API reference: <a href="/docs">/docs</a> (OpenAPI).</p>
  </div></>);
}
