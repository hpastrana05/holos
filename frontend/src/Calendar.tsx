import { useEffect, useMemo, useState } from "react";
import { api, Field } from "./shared";

type Event = { id?: string; title: string; start: string; end?: string; all_day?: boolean; color?: string; calendar_name?: string };
type SourceCalendar = { id: string; name: string; color: string; selected: boolean };
const keyFormat = new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Madrid", year: "numeric", month: "2-digit", day: "2-digit" });
const monthFormat = new Intl.DateTimeFormat("es-ES", { month: "long", year: "numeric", timeZone: "Europe/Madrid" });
const weekdays = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];
const key = (date: Date | string) => keyFormat.format(typeof date === "string" ? new Date(date) : date);
const time = (value: string) => new Intl.DateTimeFormat("es-ES", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Madrid" }).format(new Date(value));

export default function Calendar({ token, settings = false }: { token: string; settings?: boolean }) {
  const [status, setStatus] = useState<any>(null), [events, setEvents] = useState<Event[]>([]), [calendars, setCalendars] = useState<SourceCalendar[]>([]), [error, setError] = useState("");
  const [cursor, setCursor] = useState(() => new Date()), [selected, setSelected] = useState(() => key(new Date())), [creating, setCreating] = useState(false);
  const load = async (month = cursor) => { try { setError(""); const state = await api("/calendar/status", token); setStatus(state); if (state.connected) { const [sources, entries] = await Promise.all([api("/calendar/calendars", token), api(`/calendar/events/month?year=${month.getFullYear()}&month=${month.getMonth() + 1}`, token)]); setCalendars(sources); setEvents(entries); } else { setEvents([]); setCalendars([]); } } catch (reason) { setError((reason as Error).message); } };
  useEffect(() => { void load(cursor); }, [token, cursor]);
  const connect = async () => { try { location.assign((await api("/calendar/connect", token)).authorization_url); } catch (reason) { setError((reason as Error).message); } };
  const disconnect = async () => { if (!confirm("¿Desconectar Google Calendar?")) return; await api("/calendar/connection", token, { method: "DELETE" }); await load(); };
  const toggleCalendar = async (id: string) => { const next = calendars.map(calendar => calendar.id === id ? { ...calendar, selected: !calendar.selected } : calendar); setCalendars(next); try { await api("/calendar/calendars", token, { method: "PUT", body: JSON.stringify({ calendar_ids: next.filter(calendar => calendar.selected).map(calendar => calendar.id) }) }); await load(); } catch (reason) { setError((reason as Error).message); } };
  if (settings) return <section><h3>Google Calendar</h3>{!status ? <p className="state">Comprobando conexión…</p> : status.connected ? <><p className="state">Google Calendar conectado.</p><div className="calendar-sources">{calendars.map(calendar => <label key={calendar.id}><input type="checkbox" checked={calendar.selected} onChange={() => void toggleCalendar(calendar.id)} /><i style={{ backgroundColor: calendar.color }} />{calendar.name}</label>)}</div><button className="danger" onClick={() => void disconnect()}>Desconectar Google</button></> : <><p className="state">No conectado.</p><button onClick={() => void connect()}>Conectar Google</button></>}{error && <p className="error">{error}</p>}</section>;
  if (!status) return <><h2>Calendario</h2><p className="state">Cargando calendario…</p></>;
  if (!status.connected) return <><h2>Calendario</h2><p className="state">Conecta Google Calendar desde Ajustes para ver tu agenda.</p><button onClick={() => void connect()}>Conectar Google</button>{error && <p className="error">{error}</p>}</>;
  return <><div className="calendar-heading"><div><p>Agenda personal</p><h2>{monthFormat.format(cursor)}</h2></div><div className="calendar-controls"><button className="secondary" onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1))}>‹</button><button className="secondary" onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1))}>›</button><button className="secondary" onClick={() => { const now = new Date(); setCursor(now); setSelected(key(now)); }}>Hoy</button><button onClick={() => setCreating(!creating)}>{creating ? "Cerrar" : "＋ Evento"}</button></div></div>{error && <p className="error">{error}</p>}{creating && <EventForm token={token} selected={selected} done={() => { setCreating(false); void load(); }} />}<MonthGrid cursor={cursor} events={events} selected={selected} onSelect={setSelected} /><DayAgenda date={selected} events={events} /></>;
}

function MonthGrid({ cursor, events, selected, onSelect }: { cursor: Date; events: Event[]; selected: string; onSelect: (value: string) => void }) {
  const days = useMemo(() => { const first = new Date(cursor.getFullYear(), cursor.getMonth(), 1); const start = new Date(cursor.getFullYear(), cursor.getMonth(), 1 - ((first.getDay() + 6) % 7)); return Array.from({ length: 42 }, (_, index) => new Date(start.getFullYear(), start.getMonth(), start.getDate() + index)); }, [cursor]);
  const byDay = useMemo(() => events.reduce<Record<string, Event[]>>((all, event) => ({ ...all, [key(event.start)]: [...(all[key(event.start)] || []), event] }), {}), [events]);
  const today = key(new Date());
  return <section className="month-calendar"><div className="month-weekdays">{weekdays.map(day => <span key={day}>{day}</span>)}</div><div className="month-days">{days.map(day => { const id = key(day), list = byDay[id] || []; return <button type="button" key={day.toISOString()} onClick={() => onSelect(id)} className={`calendar-day ${day.getMonth() !== cursor.getMonth() ? "outside" : ""} ${id === selected ? "selected" : ""}`}><time className={id === today ? "today" : ""}>{day.getDate()}</time><div className="day-events">{list.slice(0, 3).map(event => <span className="calendar-event" style={{ backgroundColor: event.color }} key={event.id || event.start} title={`${event.calendar_name || "Calendario"}: ${event.title}`}>{event.all_day ? "" : `${time(event.start)} `}{event.title}</span>)}{list.length > 3 && <small>+{list.length - 3} más</small>}</div></button>; })}</div></section>;
}

function DayAgenda({ date, events }: { date: string; events: Event[] }) {
  const items = events.filter(event => key(event.start) === date); const title = new Intl.DateTimeFormat("es-ES", { weekday: "long", day: "numeric", month: "long" }).format(new Date(`${date}T12:00:00`));
  return <section className="day-agenda"><div><p>Eventos del día</p><h3>{title}</h3></div>{items.length ? <ul>{items.map(event => <li style={{ borderLeftColor: event.color }} key={event.id || event.start}><time>{event.all_day ? "Todo el día" : time(event.start)}</time><span><b>{event.title}</b><small>{event.calendar_name}</small></span></li>)}</ul> : <p className="state">No hay eventos este día.</p>}</section>;
}

function EventForm({ token, selected, done }: { token: string; selected: string; done: () => void }) {
  const [error, setError] = useState(""); const initial = `${selected}T09:00`;
  return <section className="calendar-form"><h3>Nuevo evento</h3><form onSubmit={async event => { event.preventDefault(); const form = new FormData(event.currentTarget); try { await api("/calendar/events", token, { method: "POST", body: JSON.stringify({ title: form.get("title"), start: form.get("start"), end: form.get("end") }) }); done(); } catch (reason) { setError((reason as Error).message); } }}><Field label="Título"><input name="title" required maxLength={300} autoFocus /></Field><Field label="Inicio"><input name="start" type="datetime-local" defaultValue={initial} required /></Field><Field label="Fin"><input name="end" type="datetime-local" defaultValue={`${selected}T10:00`} required /></Field><button>Crear evento</button>{error && <p className="error">{error}</p>}</form></section>;
}
