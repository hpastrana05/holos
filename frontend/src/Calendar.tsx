import { useEffect, useState } from "react";
import { api, Field } from "./shared";

type Event = { id?: string; title: string; start: string; end?: string; all_day?: boolean };
const dateTime = (value?: string) => value ? new Intl.DateTimeFormat("es-ES", { dateStyle: "medium", timeStyle: value.includes("T") ? "short" : undefined, timeZone: "Europe/Madrid" }).format(new Date(value)) : "—";

export default function Calendar({ token, settings = false }: { token: string; settings?: boolean }) {
  const [status, setStatus] = useState<any>(null), [events, setEvents] = useState<Event[] | null>(null), [monthEvents, setMonthEvents] = useState<Event[]>([]), [error, setError] = useState(""), [notice, setNotice] = useState("");
  const load = async () => { try { const state = await api("/calendar/status", token); setStatus(state); if (state.connected) { const [next, month] = await Promise.all([api("/calendar/events/upcoming?days=7", token), api("/calendar/events/month", token)]); setEvents(next); setMonthEvents(month); } else setEvents([]); } catch (reason) { setError((reason as Error).message); } };
  useEffect(() => { void load(); }, [token]);
  const connect = async () => { try { const { authorization_url } = await api("/calendar/connect", token); location.assign(authorization_url); } catch (reason) { setError((reason as Error).message); } };
  const disconnect = async () => { if (!confirm("¿Desconectar Google Calendar?")) return; await api("/calendar/connection", token, { method: "DELETE" }); setNotice("Calendario desconectado."); await load(); };
  if (settings) return <section><h3>Google Calendar</h3>{!status ? <p className="state">Comprobando conexión…</p> : status.connected ? <><p className="state">Google Calendar conectado.</p><button className="danger" onClick={() => void disconnect()}>Desconectar Google</button></> : <><p className="state">No conectado.</p><button onClick={() => void connect()}>Conectar Google</button></>}{error && <p className="error">{error}</p>}{notice && <p className="state">{notice}</p>}</section>;
  if (!status) return <><h2>Calendario</h2><p className="state">Cargando calendario…</p></>;
  if (!status.connected) return <><h2>Calendario</h2><p className="state">Conecta Google Calendar desde Ajustes para ver tu agenda.</p><button onClick={() => void connect()}>Conectar Google</button>{error && <p className="error">{error}</p>}</>;
  const days = new Date().getDate() && new Date(new Date().getFullYear(), new Date().getMonth() + 1, 0).getDate();
  const marked = new Set(monthEvents.map(event => new Date(event.start).getDate()));
  return <><h2>Calendario</h2>{error && <p className="error">{error}</p>}<section><h3>Próximos 7 días</h3>{events?.length ? <ul className="list">{events.map(event => <li key={event.id || event.start}><span><b>{event.title}</b><small>{dateTime(event.start)}</small></span></li>)}</ul> : <p className="state">No tienes eventos próximos.</p>}</section><section><h3>{new Intl.DateTimeFormat("es-ES", { month: "long", year: "numeric" }).format(new Date())}</h3><div className="module-grid">{Array.from({ length: days }, (_, index) => <span className="module module-calendar" key={index}><b>{index + 1}</b>{marked.has(index + 1) && <small>Evento</small>}</span>)}</div></section><EventForm token={token} done={() => void load()} /></>;
}

function EventForm({ token, done }: { token: string; done: () => void }) {
  const [error, setError] = useState("");
  return <section><h3>Crear evento</h3><form className="settings-form" onSubmit={async event => { event.preventDefault(); const form = new FormData(event.currentTarget); try { await api("/calendar/events", token, { method: "POST", body: JSON.stringify({ title: form.get("title"), start: form.get("start"), end: form.get("end"), description: form.get("description") || null }) }); event.currentTarget.reset(); done(); } catch (reason) { setError((reason as Error).message); } }}><Field label="Título"><input name="title" required maxLength={300} /></Field><Field label="Inicio"><input name="start" type="datetime-local" required /></Field><Field label="Fin"><input name="end" type="datetime-local" required /></Field><Field label="Descripción"><textarea name="description" maxLength={2000} /></Field><button>Crear evento</button>{error && <p className="error">{error}</p>}</form></section>;
}
