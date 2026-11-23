import { lazy, Suspense, useEffect, useRef, useState } from "react";
import ScreenPicker from "./ScreenPicker";
import type { Forecast } from "./WeatherScreen";
import { Icon } from "./icons";
import { euros, shortDate } from "./shared";

type Summary = {
  user_name: string;
  current_weight_kg: number | null;
  target_kcal: number | null;
  monthly_balance: number;
  recent_transactions: { id: number; date: string; kind: "income" | "expense"; amount: number }[];
};

const storageKey = "holos-screen-session";
const WeatherScreen = lazy(() => import("./WeatherScreen"));
const pages = ["Resumen personal", "Tiempo de hoy"] as const;
const clockFormat = new Intl.DateTimeFormat("es-ES", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Madrid" });
const dateFormat = new Intl.DateTimeFormat("es-ES", { weekday: "long", day: "numeric", month: "long", timeZone: "Europe/Madrid" });
const number = new Intl.NumberFormat("es-ES", { maximumFractionDigits: 1 });

function useWakeLock(enabled: boolean) {
  const [status, setStatus] = useState("");
  useEffect(() => {
    if (!enabled) return;
    if (!navigator.wakeLock) {
      setStatus("Este navegador no puede mantener la pantalla encendida.");
      return;
    }

    let lock: WakeLockSentinel | undefined;
    let stopped = false;
    let requesting = false;
    const acquire = async () => {
      if (document.visibilityState !== "visible" || requesting || (lock && !lock.released)) return;
      requesting = true;
      try {
        const acquired = await navigator.wakeLock.request("screen");
        if (stopped || document.visibilityState !== "visible") {
          await acquired.release();
          return;
        }
        lock = acquired;
        setStatus("");
        acquired.addEventListener("release", () => {
          if (!stopped && document.visibilityState === "visible") {
            setStatus("El navegador ha dejado de mantener la pantalla encendida.");
          }
        });
      } catch {
        if (!stopped) setStatus("El navegador no pudo mantener la pantalla encendida.");
      } finally {
        requesting = false;
      }
    };
    void acquire();
    document.addEventListener("visibilitychange", acquire);
    return () => {
      stopped = true;
      document.removeEventListener("visibilitychange", acquire);
      if (lock && !lock.released) void lock.release().catch(() => {});
    };
  }, [enabled]);
  return enabled ? status : "";
}

export default function Screen() {
  const [token, setToken] = useState(() => localStorage.getItem(storageKey) || "");
  const [forecast, setForecast] = useState<Forecast | null>(null);
  const [weatherError, setWeatherError] = useState("");
  const [page, setPage] = useState(0);
  const gestureStart = useRef<number | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState("");
  const [fullscreen, setFullscreen] = useState(Boolean(document.fullscreenElement));
  const [fullscreenError, setFullscreenError] = useState("");
  const [now, setNow] = useState(() => new Date());
  const wakeStatus = useWakeLock(Boolean(token));

  useEffect(() => {
    const tick = window.setInterval(() => {
      const current = new Date();
      setNow((previous) => Math.floor(current.getTime() / 60000) === Math.floor(previous.getTime() / 60000)
        ? previous : current);
    }, 1000);
    const sync = () => setFullscreen(Boolean(document.fullscreenElement));
    document.addEventListener("fullscreenchange", sync);
    return () => {
      window.clearInterval(tick);
      document.removeEventListener("fullscreenchange", sync);
    };
  }, []);

  useEffect(() => {
    if (!token) return;
    let controller: AbortController | undefined;
    const refresh = () => {
      controller?.abort();
      const request = new AbortController();
      controller = request;
      const timeout = window.setTimeout(() => {
        request.abort();
        setError("La actualización tardó demasiado.");
        setWeatherError("No se pudo actualizar el tiempo.");
      }, 15000);
      const load = async <T,>(path: string, update: (data: T) => void, report: (text: string) => void) => {
        try {
          const response = await fetch(`/api/screen/${path}`, {
            headers: { Authorization: `Bearer ${token}` },
            credentials: "omit",
            cache: "no-store",
            signal: request.signal,
          });
          if (request.signal.aborted) return;
          if (response.status === 401 || response.status === 403) {
            request.abort();
            localStorage.removeItem(storageKey);
            setSummary(null);
            setForecast(null);
            setToken("");
            setError("La sesión ha terminado. Elige un usuario.");
            return;
          }
          if (!response.ok) throw new Error();
          const data: T = await response.json();
          if (!request.signal.aborted) {
            update(data);
            report("");
          }
        } catch {
          if (controller === request && !request.signal.aborted) report(path === "weather" ? "No se pudo actualizar el tiempo." : "No se pudo actualizar el resumen.");
        }
      };
      void Promise.all([
        load<Summary>("summary", setSummary, setError),
        load<Forecast>("weather", setForecast, setWeatherError),
      ]).finally(() => window.clearTimeout(timeout));
    };
    refresh();
    const interval = window.setInterval(refresh, 60000);
    return () => {
      const request = controller;
      controller = undefined;
      request?.abort();
      window.clearInterval(interval);
    };
  }, [token]);

  useEffect(() => {
    if (!token) return;
    const timer = window.setTimeout(() => setPage((page + 1) % pages.length), 20000);
    return () => window.clearTimeout(timer);
  }, [token, page]);

  const toggleFullscreen = async () => {
    setFullscreenError("");
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await document.documentElement.requestFullscreen();
    } catch {
      setFullscreenError("No se pudo activar el modo de pantalla completa.");
    }
  };

  const forget = () => {
    localStorage.removeItem(storageKey);
    setToken("");
    setSummary(null);
    setForecast(null);
    setWeatherError("");
    setPage(0);
    setError("");
  };

  return (
    <main className="screen">
      <div className="screen-toolbar">
        <a href="/" aria-label="Volver a Holos"><Icon name="dashboard" /></a>
        {token && <button type="button" className="secondary" onClick={forget}>Cambiar de usuario</button>}
        {document.fullscreenEnabled && <button type="button" className="secondary" onClick={toggleFullscreen}>
          {fullscreen ? "Salir de pantalla completa" : "Pantalla completa"}
        </button>}
      </div>
      {!token ? <ScreenPicker onSession={value => {
        localStorage.setItem(storageKey, value);
        setPage(0);
        setError("");
        setToken(value);
      }} /> : (
        <div className="screen-slides"
          onTouchStart={event => { gestureStart.current = event.touches[0].clientX; }}
          onTouchCancel={() => { gestureStart.current = null; }}
          onTouchEnd={event => {
            const start = gestureStart.current;
            gestureStart.current = null;
            if (start === null) return;
            const distance = event.changedTouches[0].clientX - start;
            if (Math.abs(distance) >= 45) {
              setPage(current => (current + (distance < 0 ? 1 : pages.length - 1)) % pages.length);
            }
          }}>
          {page === 1 ? <Suspense fallback={<p className="state">Cargando el tiempo…</p>}>
            <WeatherScreen forecast={forecast} error={weatherError} />
          </Suspense> : <>
            <div className="screen-clock">
              <time dateTime={now.toISOString()}>{clockFormat.format(now)}</time>
              <p>{dateFormat.format(now)}{summary && ` · ${summary.user_name}`}</p>
            </div>
            {summary ? (
              <div className="screen-grid">
                <section className="screen-health module-health">
                  <h2><Icon name="health" /> Salud</h2>
                  <dl>
                    <div><dt>Peso actual</dt><dd>{summary.current_weight_kg === null ? "—" : `${number.format(summary.current_weight_kg)} kg`}</dd></div>
                    <div><dt>Objetivo diario</dt><dd>{summary.target_kcal === null ? "—" : `${number.format(summary.target_kcal)} kcal`}</dd></div>
                  </dl>
                </section>
                <section className="screen-finance module-finance">
                  <h2><Icon name="finance" /> Finanzas</h2>
                  <dl><div><dt>Balance del mes</dt><dd>{euros.format(summary.monthly_balance)}</dd></div></dl>
                </section>
                <section className="screen-recent module-finance">
                  <h2>Últimos movimientos</h2>
                  {summary.recent_transactions.length ? (
                    <ul className="screen-transactions">
                      {summary.recent_transactions.map(({ id, date, kind, amount }) => (
                        <li key={id}><time dateTime={date}>{shortDate(date)}</time><b>{euros.format(kind === "income" ? amount : -amount)}</b></li>
                      ))}
                    </ul>
                  ) : <p className="state">Aún no hay movimientos.</p>}
                </section>
                <section className="screen-house module-house">
                  <h2><Icon name="house" /> Casa</h2>
                  <p className="state">Consumo y dispositivos · Próximamente</p>
                </section>
              </div>
            ) : !error && <p className="state" role="status">Cargando resumen…</p>}
          </>}
          <nav className="screen-pages" aria-label="Pantallas">
            {pages.map((label, index) => <button className="secondary" key={label} type="button"
              aria-current={page === index ? "page" : undefined} onClick={() => setPage(index)}>{label}</button>)}
          </nav>
        </div>
      )}
      {(error || fullscreenError || wakeStatus) && <p className="screen-status state" role="status">
        {[error, fullscreenError, wakeStatus].filter(Boolean).join(" ")}
      </p>}
    </main>
  );
}
