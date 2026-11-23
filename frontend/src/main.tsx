import { lazy, Suspense, useState } from "react";
import { createRoot } from "react-dom/client";
import { Icon, type IconName } from "./icons";
import Login from "./Login";
import "./style.css";

const Screen = lazy(() => import("./Screen"));
const Dashboard = lazy(() => import("./views").then(({ Dashboard }) => ({ default: Dashboard })));
const Health = lazy(() => import("./views").then(({ Health }) => ({ default: Health })));
const Finance = lazy(() => import("./views").then(({ Finance }) => ({ default: Finance })));

if (import.meta.env.PROD && "serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    void navigator.serviceWorker.register("/sw.js").catch(console.error);
  });
}

type Tab = "dashboard" | "health" | "finance";
const modules: { icon: IconName; label: string; tab?: Tab }[] = [
  { icon: "health", label: "Salud", tab: "health" },
  { icon: "finance", label: "Finanzas", tab: "finance" },
  { icon: "nutrition", label: "Nutrición" },
  { icon: "calendar", label: "Calendario" },
  { icon: "house", label: "Casa" },
  { icon: "chat", label: "Chat" },
];
const navigation = [{ icon: "dashboard", label: "Inicio", tab: "dashboard" }, ...modules.filter(({ tab }) => tab)] as
  { icon: IconName; label: string; tab: Tab }[];

function Launcher({ open }: { open: (tab: Tab) => void }) {
  const now = new Date();
  const hour = now.getHours();
  const greeting = hour < 6 || hour >= 21 ? "Buenas noches" : hour < 13 ? "Buenos días" : "Buenas tardes";
  return (
    <>
      <header className="launcher-header">
        <p>{greeting}</p>
        <h1>Tu Holos</h1>
        <time>{new Intl.DateTimeFormat("es-ES", { dateStyle: "full" }).format(now)}</time>
      </header>
      <div className="module-grid" aria-label="Módulos">
        {modules.map(({ icon, label, tab }) => (
          <button type="button" className={`module module-${icon}`} key={icon}
            disabled={!tab} onClick={() => tab && open(tab)}>
            <span className="module-icon"><Icon name={icon} /></span>
            <span className="module-label">{label}</span>
            {!tab && <small>Próximamente</small>}
          </button>
        ))}
      </div>
    </>
  );
}

function App() {
  const [token, setToken] = useState(() => localStorage.getItem("holos-token") || "");
  const [tab, setTab] = useState<Tab>("dashboard");
  const open = (next: Tab) => {
    setTab(next);
    window.scrollTo(0, 0);
  };
  if (!token) {
    return <Login onLogin={(value) => {
      localStorage.setItem("holos-token", value);
      setToken(value);
    }} />;
  }
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand"><Icon name="dashboard" /> Holos</div>
        <nav aria-label="Navegación principal">
          {navigation.map(({ icon, label, tab: destination }) => (
            <button key={destination} type="button"
              aria-current={tab === destination ? "page" : undefined}
              onClick={() => open(destination)}>
              <Icon name={icon} /><span>{label}</span>
            </button>
          ))}
          <a href="/pantalla"><Icon name="screen" /><span>Pantalla</span></a>
          <button type="button" onClick={() => {
            localStorage.removeItem("holos-token");
            setToken("");
            open("dashboard");
          }}><Icon name="logout" /><span>Salir</span></button>
        </nav>
      </aside>
      <main className={`workspace module-${tab}`}>
        {tab === "dashboard" && <Launcher open={open} />}
        <Suspense fallback={<p className="state" role="status">Cargando…</p>}>
          {tab === "dashboard" && <Dashboard token={token} />}
          {tab === "health" && <Health token={token} />}
          {tab === "finance" && <Finance token={token} />}
        </Suspense>
      </main>
    </div>
  );
}

const isScreen = location.pathname.replace(/\/$/, "") === "/pantalla";
createRoot(document.getElementById("root")!).render(
  isScreen ? (
    <Suspense fallback={<p className="screen-status" role="status">Cargando pantalla…</p>}>
      <Screen />
    </Suspense>
  ) : <App />,
);
