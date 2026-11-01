import { useEffect, useState } from "react";
import Overview from "./pages/Overview";
import Containers from "./pages/Containers";
import Experiments from "./pages/Experiments";
import Lab from "./pages/Lab";
import Diagnostics from "./pages/Diagnostics";
import Logs from "./pages/Logs";
import Docs from "./pages/Docs";

export type PageKey =
  | "Overview"
  | "Containers"
  | "Experiment Lab"
  | "OS Laboratory"
  | "System Diagnostics"
  | "Logs & Events"
  | "Documentation";

const NAV_ITEMS: { key: PageKey; icon: string; label: string; badge?: string }[] = [
  { key: "Overview", icon: "📊", label: "Overview" },
  { key: "Containers", icon: "📦", label: "Containers" },
  { key: "Experiment Lab", icon: "🔬", label: "Experiment Lab" },
  { key: "OS Laboratory", icon: "🧪", label: "OS Laboratory", badge: "Sim" },
  { key: "System Diagnostics", icon: "🩺", label: "System Diagnostics" },
  { key: "Logs & Events", icon: "📜", label: "Logs & Events" },
  { key: "Documentation", icon: "📖", label: "Documentation" },
];

const PAGES: Record<PageKey, () => JSX.Element> = {
  Overview,
  Containers,
  "Experiment Lab": Experiments,
  "OS Laboratory": Lab,
  "System Diagnostics": Diagnostics,
  "Logs & Events": Logs,
  Documentation: Docs,
};

function getPageFromHash(): PageKey {
  const raw = decodeURIComponent(location.hash.replace(/^#\/?/, "")).trim();
  const match = Object.keys(PAGES).find((k) => k.toLowerCase() === raw.toLowerCase());
  return (match as PageKey) || "Overview";
}

export default function App() {
  const [page, setPage] = useState<PageKey>(getPageFromHash);

  // Synchronize hash changes (back/forward navigation & direct links)
  useEffect(() => {
    const onHashChange = () => {
      setPage(getPageFromHash());
    };
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const navigateTo = (key: PageKey) => {
    setPage(key);
    location.hash = encodeURIComponent(key);
  };

  const PageComponent = PAGES[page] ?? Overview;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-logo">CRIS</div>
          <div className="brand-meta">
            <span className="brand-title">Resource Isolation</span>
            <span className="brand-sub">Linux Namespaces & cgroups v2</span>
          </div>
        </div>

        <nav className="nav-menu" aria-label="Primary Navigation">
          {NAV_ITEMS.map((item) => {
            const active = item.key === page;
            return (
              <button
                key={item.key}
                className={`nav-item ${active ? "active" : ""}`}
                aria-current={active ? "page" : undefined}
                onClick={() => navigateTo(item.key)}
              >
                <span className="nav-icon">{item.icon}</span>
                <span className="nav-label">{item.label}</span>
                {item.badge && <span className="nav-badge">{item.badge}</span>}
              </button>
            );
          })}
        </nav>

        <div className="sidebar-footer">
          <div className="status-indicator">
            <span className="status-dot live"></span>
            <span className="status-text">CRIS Control Plane</span>
          </div>
          <div className="host-info">FastAPI :8000 · v0.1.0</div>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div className="breadcrumbs">
            <span className="crumb-root">CRIS</span>
            <span className="crumb-sep">/</span>
            <span className="crumb-active">{page}</span>
          </div>
          <div className="topbar-actions">
            <span className="platform-tag">Linux Isolation Platform</span>
          </div>
        </header>

        <div className="content-area">
          <PageComponent />
        </div>
      </main>
    </div>
  );
}
