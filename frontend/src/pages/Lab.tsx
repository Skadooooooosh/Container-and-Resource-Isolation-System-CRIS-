import { useState } from "react";
import { api, post } from "../services/api";
import { Err } from "../usePoll";

const PID_COLORS: Record<string, string> = {
  P1: "#38bdf8",
  P2: "#10b981",
  P3: "#f59e0b",
  P4: "#ec4899",
  P5: "#a855f7",
  P6: "#6366f1",
  IDLE: "#475569",
};

function getPidColor(pid: string, idx: number) {
  if (pid === "IDLE") return "#334155";
  if (PID_COLORS[pid]) return PID_COLORS[pid];
  const palette = ["#0284c7", "#059669", "#d97706", "#db2777", "#7c3aed", "#4f46e5"];
  return palette[idx % palette.length];
}

const SAMPLES: Record<string, { path: string; body: any; label: string; description: string }> = {
  scheduling: {
    label: "CPU Scheduling Algorithms",
    description: "Simulates FCFS, SJF, SRTF, Priority, Preemptive Priority, Round Robin, and MLFQ.",
    path: "/lab/scheduling",
    body: {
      algorithm: "rr",
      quantum: 2,
      processes: [
        { pid: "P1", arrival: 0, burst: 5, priority: 2 },
        { pid: "P2", arrival: 1, burst: 3, priority: 1 },
        { pid: "P3", arrival: 2, burst: 8, priority: 4 },
        { pid: "P4", arrival: 3, burst: 6, priority: 3 },
      ],
    },
  },
  paging: {
    label: "Page Replacement Algorithms",
    description: "FIFO, LRU, and Optimal step-by-step frame allocation and fault calculation.",
    path: "/lab/memory/replacement",
    body: {
      algorithm: "lru",
      frames: 3,
      references: [7, 0, 1, 2, 0, 3, 0, 4, 2, 3, 0, 3, 2, 1, 2, 0, 1, 7, 0, 1],
    },
  },
  banker: {
    label: "Banker's Algorithm & Resource Safety",
    description: "Calculates Need matrix, Available vectors, and finds safe execution sequences.",
    path: "/lab/deadlock/banker",
    body: {
      available: [3, 3, 2],
      maximum: [
        [7, 5, 3],
        [3, 2, 2],
        [9, 0, 2],
        [2, 2, 2],
        [4, 3, 3],
      ],
      allocation: [
        [0, 1, 0],
        [2, 0, 0],
        [3, 0, 2],
        [2, 1, 1],
        [0, 0, 2],
      ],
    },
  },
  deadlock_detect: {
    label: "Deadlock Detection Algorithm",
    description: "Examines allocation and request matrices to identify cycles and deadlocked processes.",
    path: "/lab/deadlock/detect",
    body: {
      available: [0, 0, 0],
      allocation: [
        [0, 1, 0],
        [2, 0, 0],
        [3, 0, 3],
        [2, 1, 1],
        [0, 0, 2],
      ],
      request: [
        [0, 0, 0],
        [2, 0, 2],
        [0, 0, 0],
        [1, 0, 0],
        [0, 0, 2],
      ],
    },
  },
  disk: {
    label: "Disk Arm Head Scheduling",
    description: "Visualizes arm traversal distance for FCFS, SSTF, SCAN, C-SCAN, LOOK, and C-LOOK.",
    path: "/lab/disk-scheduling",
    body: {
      algorithm: "look",
      head: 53,
      disk_size: 200,
      direction: "down",
      requests: [98, 183, 37, 122, 14, 124, 65, 67],
    },
  },
};

export default function Lab() {
  const [activeKey, setActiveKey] = useState("scheduling");
  const [jsonText, setJsonText] = useState(JSON.stringify(SAMPLES.scheduling.body, null, 2));
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [syncResult, setSyncResult] = useState<any>(null);

  const handleSelectModule = (key: string) => {
    setActiveKey(key);
    setJsonText(JSON.stringify(SAMPLES[key].body, null, 2));
    setResult(null);
    setError(null);
  };

  const handleSimulate = async () => {
    try {
      setError(null);
      const parsed = JSON.parse(jsonText);
      const res = await post(SAMPLES[activeKey].path, parsed);
      setResult(res);
    } catch (e: any) {
      setError(e.message ?? String(e));
      setResult(null);
    }
  };

  const handleSyncDemo = async (url: string) => {
    try {
      setError(null);
      const res = await api(url);
      setSyncResult(res);
    } catch (e: any) {
      setError(e.message ?? String(e));
    }
  };

  // Gantt Chart Calculations
  const totalGanttTime = result?.gantt?.length
    ? Math.max(1, result.gantt[result.gantt.length - 1].end)
    : 1;

  return (
    <>
      <div className="card-header">
        <h2>
          <span>Operating System Laboratory</span>
          <span className="pill warn">Simulated Educational Models</span>
        </h2>
      </div>

      <p style={{ color: "var(--text-muted)", marginTop: "-8px", marginBottom: "18px" }}>
        Interactive visualizers for foundational OS algorithms. These models demonstrate textbook behavior
        (Silberschatz / Tanenbaum) with full state transparency.
      </p>

      {/* Simulator Selector & Parameters */}
      <div className="card">
        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", marginBottom: "14px" }}>
          {Object.entries(SAMPLES).map(([k, s]) => (
            <button
              key={k}
              className={`btn sm ${activeKey === k ? "primary" : ""}`}
              onClick={() => handleSelectModule(k)}
            >
              {s.label}
            </button>
          ))}
        </div>

        <p style={{ fontSize: "12px", color: "var(--text-dim)", marginBottom: "12px" }}>
          {SAMPLES[activeKey].description}
        </p>

        <div className="form-group" style={{ marginBottom: "12px" }}>
          <label>Algorithm Input Parameters (JSON)</label>
          <textarea
            value={jsonText}
            onChange={(e) => setJsonText(e.target.value)}
            style={{ minHeight: "130px" }}
          />
        </div>

        <div style={{ display: "flex", gap: "8px" }}>
          <button className="btn primary" onClick={handleSimulate}>
            Run Simulator
          </button>
          <button className="btn" onClick={() => handleSelectModule(activeKey)}>
            Reset Defaults
          </button>
        </div>
      </div>

      {/* Real Synchronization Multi-Threaded Lab */}
      <div className="card" style={{ background: "rgba(0,0,0,0.2)" }}>
        <h4 className="card-title" style={{ fontSize: "13px", marginBottom: "8px" }}>
          Concurrency & Synchronization Experiments (Python Multi-Threading)
        </h4>
        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
          <button className="btn sm" onClick={() => handleSyncDemo("/lab/synchronization/race?schedule=interleaved")}>
            Race Condition (Interleaved)
          </button>
          <button className="btn sm" onClick={() => handleSyncDemo("/lab/synchronization/race?schedule=serial")}>
            Race Condition (Serial)
          </button>
          <button className="btn sm" onClick={() => handleSyncDemo("/lab/synchronization/producer-consumer")}>
            Producer–Consumer (Bounded Buffer)
          </button>
          <button className="btn sm" onClick={() => handleSyncDemo("/lab/synchronization/dining-philosophers?strategy=naive")}>
            Philosophers (Naive / Deadlock prone)
          </button>
          <button className="btn sm" onClick={() => handleSyncDemo("/lab/synchronization/dining-philosophers?strategy=ordered")}>
            Philosophers (Resource Hierarchy)
          </button>
        </div>

        {syncResult && (
          <div style={{ marginTop: "12px" }}>
            <span className="platform-tag" style={{ color: "var(--accent)" }}>Concurrency Output</span>
            <pre style={{ marginTop: "8px" }}>{JSON.stringify(syncResult, null, 2)}</pre>
          </div>
        )}
      </div>

      <Err msg={error} onDismiss={() => setError(null)} />

      {/* Visualizer 1: CPU Scheduling Gantt Chart & Table */}
      {result?.gantt && (
        <div className="card">
          <div className="card-header">
            <h4 className="card-title">Gantt Chart Trajectory</h4>
            <span className="mono" style={{ fontSize: "11px", color: "var(--accent)" }}>
              Total Horizon: {totalGanttTime} time units
            </span>
          </div>

          <div className="gantt-chart">
            {result.gantt.map((g: any, i: number) => {
              const widthPct = ((g.end - g.start) / totalGanttTime) * 100;
              const bg = getPidColor(g.pid, i);
              return (
                <div
                  key={i}
                  className="gantt-block"
                  style={{ width: `${widthPct}%`, background: bg }}
                  title={`${g.pid}: [${g.start} → ${g.end}] (duration ${g.end - g.start})`}
                >
                  {widthPct > 5 ? `${g.pid} (${g.start}-${g.end})` : g.pid}
                </div>
              );
            })}
          </div>

          <div className="metrics-grid" style={{ marginTop: "14px", marginBottom: "14px" }}>
            <div className="metric-card">
              <span className="metric-label">Average Waiting Time</span>
              <span className="metric-value">{result.avg_waiting}</span>
              <span className="metric-sub">Mean time spent in ready queue</span>
            </div>
            <div className="metric-card">
              <span className="metric-label">Average Turnaround Time</span>
              <span className="metric-value">{result.avg_turnaround}</span>
              <span className="metric-sub">Completion time minus arrival time</span>
            </div>
            <div className="metric-card">
              <span className="metric-label">Average Response Time</span>
              <span className="metric-value">{result.avg_response}</span>
              <span className="metric-sub">Time from arrival to first execution</span>
            </div>
          </div>

          {result.table && (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    {Object.keys(result.table[0]).map((col) => (
                      <th key={col}>{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.table.map((row: any, i: number) => (
                    <tr key={i}>
                      {Object.entries(row).map(([k, val]: any) => (
                        <td key={k} className={k === "pid" ? "mono" : undefined}>
                          {k === "pid" ? (
                            <span
                              className="pill"
                              style={{
                                background: getPidColor(val, i),
                                color: "#fff",
                                fontWeight: 700,
                              }}
                            >
                              {val}
                            </span>
                          ) : (
                            String(val)
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Visualizer 2: Page Replacement Step-by-Step Memory Frames */}
      {result?.steps && (
        <div className="card">
          <div className="card-header">
            <h4 className="card-title">Step-by-Step Memory Frame Trajectory</h4>
            <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
              <span className="pill bad">Total Faults: {result.faults}</span>
              <span className="pill ok">Total Hits: {result.references?.length - result.faults}</span>
            </div>
          </div>

          <p style={{ fontSize: "12px", color: "var(--text-muted)", marginBottom: "12px" }}>
            Reference string traversal. Red indicates a page fault (disk page fetch); green indicates a cache hit.
          </p>

          <div className="frames-container">
            {result.steps.map((st: any, idx: number) => (
              <div className="frame-step" key={idx}>
                <span className="mono" style={{ fontSize: "11px", fontWeight: 700 }}>
                  Ref: {st.page}
                </span>
                {st.frames.map((frameVal: any, fIdx: number) => (
                  <div
                    key={fIdx}
                    className={`frame-slot ${frameVal == null ? "empty" : ""}`}
                  >
                    {frameVal != null ? frameVal : "—"}
                  </div>
                ))}
                <span className={`fault-tag ${st.fault ? "fault" : "hit"}`}>
                  {st.fault ? "FAULT" : "HIT"}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Visualizer 3: Banker's Algorithm & Safe Sequences */}
      {result?.need && (
        <div className="card">
          <div className="card-header">
            <h4 className="card-title">Banker's Resource Safety Analysis</h4>
            <span className={`pill ${result.safe ? "ok" : "bad"}`}>
              {result.safe ? "System is in SAFE State" : "UNSAFE State (Potential Deadlock)"}
            </span>
          </div>

          {result.safe && result.sequence && (
            <div style={{ margin: "14px 0", display: "flex", alignItems: "center", gap: "8px" }}>
              <span style={{ fontWeight: 600, color: "var(--text-muted)" }}>Safe Execution Sequence:</span>
              <div style={{ display: "flex", gap: "6px" }}>
                {result.sequence.map((pid: string, idx: number) => (
                  <span key={idx} className="pill ok mono" style={{ fontSize: "12px" }}>
                    {pid} {idx < result.sequence.length - 1 ? "→" : ""}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Formatted Need Matrix */}
          <h5 style={{ margin: "12px 0 6px", color: "var(--text-muted)", fontSize: "11.5px" }}>
            Calculated Need Matrix (Max - Allocation)
          </h5>
          <div className="table-wrap" style={{ marginBottom: "14px" }}>
            <table>
              <thead>
                <tr>
                  <th>Process</th>
                  <th>Need Vector</th>
                </tr>
              </thead>
              <tbody>
                {result.need.map((row: number[], i: number) => (
                  <tr key={i}>
                    <td className="mono" style={{ fontWeight: 600 }}>P{i}</td>
                    <td className="mono">[{row.join(", ")}]</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Visualizer 4: Deadlock Detection */}
      {result?.deadlocked !== undefined && (
        <div className="card">
          <div className="card-header">
            <h4 className="card-title">Deadlock Detection Report</h4>
            <span className={`pill ${result.deadlocked ? "bad" : "ok"}`}>
              {result.deadlocked ? "Deadlock Detected!" : "No Deadlock (All Complete)"}
            </span>
          </div>
          {result.deadlocked_processes && (
            <p style={{ color: "var(--bad)" }}>
              <strong>Deadlocked Processes:</strong> {result.deadlocked_processes.length ? result.deadlocked_processes.join(", ") : "None"}
            </p>
          )}
        </div>
      )}

      {/* Visualizer 5: Disk Scheduling Arm Movement */}
      {result?.seek_distance !== undefined && (
        <div className="card">
          <div className="card-header">
            <h4 className="card-title">Disk Arm Movement Track</h4>
            <span className="pill info mono">
              Total Seek Distance: {result.seek_distance} Cylinders
            </span>
          </div>

          <p style={{ fontSize: "12px", color: "var(--text-muted)", marginBottom: "8px" }}>
            Head Start: <span className="mono">{result.head_start}</span> · Direction: <span className="mono">{result.direction}</span>
          </p>

          <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap", margin: "14px 0" }}>
            <span style={{ fontWeight: 600, color: "var(--text-muted)", fontSize: "12px" }}>Arm Trajectory:</span>
            {result.sequence?.map((cyl: number, i: number) => (
              <span key={i} className="pill info mono" style={{ fontSize: "11px" }}>
                {cyl} {i < result.sequence.length - 1 ? "→" : ""}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Raw Result Inspector */}
      {result && (
        <div className="card" style={{ background: "rgba(0,0,0,0.15)" }}>
          <h4 className="card-title" style={{ fontSize: "12px", marginBottom: "8px" }}>
            Full Simulator State (JSON Output)
          </h4>
          <pre>{JSON.stringify(result, null, 2)}</pre>
        </div>
      )}
    </>
  );
}
