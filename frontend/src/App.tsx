import { useEffect, useState } from "react";
import Overview from "./pages/Overview";
import Containers from "./pages/Containers";
import Experiments from "./pages/Experiments";
import Lab from "./pages/Lab";
import Diagnostics from "./pages/Diagnostics";
import Logs from "./pages/Logs";
import Docs from "./pages/Docs";

const PAGES: Record<string, () => JSX.Element> = {
  Overview, Containers, "Experiment Lab": Experiments, "OS Laboratory": Lab, "System Diagnostics": Diagnostics, "Logs & Events": Logs, Documentation: Docs,
};

export default function App() {
  const [page, setPage] = useState(() => decodeURIComponent(location.hash.slice(1)) || "Overview");
  useEffect(() => { location.hash = encodeURIComponent(page); }, [page]);
  const Page = PAGES[page] ?? Overview;
  return (
    <div className="app">
      <nav aria-label="Primary">
        <h1>CRIS</h1>
        {Object.keys(PAGES).map((p) => (
          <button key={p} className={p === page ? "on" : ""} aria-current={p === page ? "page" : undefined} onClick={() => setPage(p)}>{p}</button>
        ))}
      </nav>
      <main><Page /></main>
    </div>
  );
}
