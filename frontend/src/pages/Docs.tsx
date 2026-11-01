export default function Docs() {
  return (
    <>
      <div className="card-header">
        <h2>Documentation & System Architecture</h2>
        <a className="btn sm primary" href="/docs" target="_blank" rel="noreferrer">
          Interactive OpenAPI Docs ↗
        </a>
      </div>

      <div className="card">
        <h4 className="card-title" style={{ marginBottom: "10px" }}>System Overview</h4>
        <p style={{ color: "var(--text-muted)", lineHeight: 1.6 }}>
          <strong>CRIS (Container & Resource Isolation System)</strong> is an operating system engineering platform
          demonstrating Linux isolation mechanisms: <strong>Linux namespaces</strong> (PID, Mount, UTS, IPC, Network, User)
          and <strong>cgroups v2</strong> (CPU quota bandwidth, Memory limits, and PID concurrency caps).
        </p>

        <div className="metrics-grid" style={{ margin: "16px 0" }}>
          <div className="metric-card">
            <span className="metric-label">React UI & Dashboard</span>
            <span style={{ fontSize: "12px", color: "var(--text-main)" }}>
              Vite + React + TypeScript + Recharts telemetry visualization.
            </span>
          </div>
          <div className="metric-card">
            <span className="metric-label">FastAPI Control Plane</span>
            <span style={{ fontSize: "12px", color: "var(--text-main)" }}>
              REST API, SQLite persistence, /proc liveness verification, supervisor threads.
            </span>
          </div>
          <div className="metric-card">
            <span className="metric-label">Native C Launcher</span>
            <span style={{ fontSize: "12px", color: "var(--text-main)" }}>
              <code>cris_run</code>: clone(2) namespaces, cgroup attach before exec, PID-1 orphan reaper.
            </span>
          </div>
          <div className="metric-card">
            <span className="metric-label">Linux Kernel</span>
            <span style={{ fontSize: "12px", color: "var(--text-main)" }}>
              Enforces real namespace isolation and cgroup limits; reports counters.
            </span>
          </div>
        </div>
      </div>

      <div className="card">
        <h4 className="card-title" style={{ marginBottom: "10px" }}>Key API Endpoints</h4>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Method</th>
                <th>Endpoint</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="mono" style={{ color: "var(--ok)" }}>GET</td>
                <td className="mono">/api/system/capabilities</td>
                <td>Returns live kernel probe results (namespaces, cgroups v2, delegation)</td>
              </tr>
              <tr>
                <td className="mono" style={{ color: "var(--ok)" }}>GET</td>
                <td className="mono">/api/system/metrics</td>
                <td>Live host CPU, memory, and container summary counters</td>
              </tr>
              <tr>
                <td className="mono" style={{ color: "var(--ok)" }}>GET</td>
                <td className="mono">/api/containers</td>
                <td>List all managed containers with requested and effective limits</td>
              </tr>
              <tr>
                <td className="mono" style={{ color: "var(--accent)" }}>POST</td>
                <td className="mono">/api/containers</td>
                <td>Create a new container and cgroup directory</td>
              </tr>
              <tr>
                <td className="mono" style={{ color: "var(--accent)" }}>POST</td>
                <td className="mono">/api/containers/&#123;id&#125;/start</td>
                <td>Launch workload inside container with requested namespaces & cgroups</td>
              </tr>
              <tr>
                <td className="mono" style={{ color: "var(--warn)" }}>POST</td>
                <td className="mono">/api/containers/&#123;id&#125;/stop</td>
                <td>Gracefully terminate container process tree (idempotent)</td>
              </tr>
              <tr>
                <td className="mono" style={{ color: "var(--bad)" }}>DELETE</td>
                <td className="mono">/api/containers/&#123;id&#125;</td>
                <td>Remove stopped or failed container and purge cgroup directory</td>
              </tr>
              <tr>
                <td className="mono" style={{ color: "var(--accent)" }}>POST</td>
                <td className="mono">/api/experiments</td>
                <td>Run reproducible isolation benchmarks with statistical analysis</td>
              </tr>
              <tr>
                <td className="mono" style={{ color: "var(--accent)" }}>POST</td>
                <td className="mono">/api/lab/scheduling</td>
                <td>Simulate CPU scheduling (FCFS, SJF, SRTF, RR, Priority, MLFQ)</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <h4 className="card-title" style={{ marginBottom: "10px" }}>Security & Implementation Boundaries</h4>
        <div style={{ display: "flex", flexDirection: "column", gap: "8px", fontSize: "12.5px", color: "var(--text-muted)" }}>
          <div>
            <strong style={{ color: "var(--warn)" }}>• Filesystem Sandbox:</strong> Mount namespace creates a private
            <code>/proc</code> mount; it is not a chroot/pivot_root image sandbox. Container workloads share the host rootfs.
          </div>
          <div>
            <strong style={{ color: "var(--warn)" }}>• Seccomp Filtering:</strong> Syscall filtering is not enabled. Workloads can
            execute any permitted Linux system call.
          </div>
          <div>
            <strong style={{ color: "var(--warn)" }}>• Networking:</strong> Network namespaces are initialized empty without veth
            pairs or bridge devices (loopback is down).
          </div>
          <div>
            <strong style={{ color: "var(--ok)" }}>• PID Isolation:</strong> PID namespaces isolate the process table. The native
            launcher reaps orphans as PID 1, preventing runaway zombie processes.
          </div>
          <div>
            <strong style={{ color: "var(--ok)" }}>• Resource Enforcement:</strong> CPU and memory bandwidth limits are strictly
            enforced by cgroups v2; effective values are read back directly from kernel files.
          </div>
        </div>
      </div>
    </>
  );
}
