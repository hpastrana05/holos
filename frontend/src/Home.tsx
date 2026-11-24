import { useEffect, useMemo, useState } from "react";
import { Icon } from "./icons";
import { api, Field } from "./shared";

type Entity = { id: number; entity_id: string; display_name: string; room: string; domain: string; sensitive: boolean; state?: string; available: boolean; consumption?: number; consumption_unit?: string };
type Status = { connected: boolean; entities: Entity[]; error?: string };

export default function Home({ token, settings = false }: { token: string; settings?: boolean }) {
  const [status, setStatus] = useState<Status | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<number | null>(null);
  const [discovered, setDiscovered] = useState<any[] | null>(null);
  const [editing, setEditing] = useState<Entity | null>(null);
  const load = () => api("/home/status", token).then(setStatus).catch((reason: Error) => setError(reason.message));
  useEffect(() => { void load(); }, [token]);
  const byRoom = useMemo(() => Object.entries((status?.entities || []).reduce<Record<string, Entity[]>>((groups, entity) => ({ ...groups, [entity.room]: [...(groups[entity.room] || []), entity] }), {})), [status]);
  const control = async (entity: Entity, action: string) => {
    if (entity.sensitive && !confirm(`¿Confirmas cambiar ${entity.display_name}?`)) return;
    setBusy(entity.id); setError("");
    try { await api(`/home/entities/${entity.id}/control`, token, { method: "POST", body: JSON.stringify({ action }) }); await load(); }
    catch (reason) { setError((reason as Error).message); }
    finally { setBusy(null); }
  };
  const discover = async () => { setError(""); try { setDiscovered(await api("/home/discover", token)); } catch (reason) { setError((reason as Error).message); } };
  const add = async (entity: any) => {
    const name = String(entity.attributes?.friendly_name || entity.entity_id);
    try { await api("/home/entities", token, { method: "POST", body: JSON.stringify({ entity_id: entity.entity_id, display_name: name, room: "Sin estancia" }) }); setDiscovered(null); await load(); }
    catch (reason) { setError((reason as Error).message); }
  };
  const save = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault(); if (!editing) return;
    const form = new FormData(event.currentTarget);
    try { await api(`/home/entities/${editing.id}`, token, { method: "PUT", body: JSON.stringify({ display_name: form.get("display_name"), room: form.get("room"), sensitive: form.has("sensitive") }) }); setEditing(null); await load(); }
    catch (reason) { setError((reason as Error).message); }
  };
  const remove = async (entity: Entity) => { if (!confirm(`¿Quitar ${entity.display_name} de la lista permitida?`)) return; await api(`/home/entities/${entity.id}`, token, { method: "DELETE" }); await load(); };
  if (settings) return <section className="home-settings"><h3>Casa · Home Assistant</h3><p className={`state ${status?.connected ? "" : "error"}`}>{status?.connected ? "Home Assistant conectado." : status?.error || "Comprobando conexión…"}</p>
    <button type="button" onClick={discover}>Descubrir entidades</button>
    {discovered && <ul className="list home-discovery">{discovered.map(item => <li key={item.entity_id}><span><b>{item.attributes?.friendly_name || item.entity_id}</b><small>{item.entity_id} · {item.state}</small></span><button type="button" className="secondary" onClick={() => add(item)}>Permitir</button></li>)}</ul>}
    <ul className="list">{status?.entities.map(entity => <li key={entity.id}><span><b>{entity.display_name}</b><small>{entity.entity_id} · {entity.room}{entity.sensitive ? " · sensible" : ""}</small></span><span className="actions"><button className="secondary" onClick={() => setEditing(entity)}>Editar</button><button className="danger" onClick={() => void remove(entity)}>Quitar</button></span></li>)}</ul>
    {editing && <form className="settings-form" onSubmit={save}><h4>Editar entidad</h4><Field label="Nombre visible"><input name="display_name" defaultValue={editing.display_name} required maxLength={160} /></Field><Field label="Estancia"><input name="room" defaultValue={editing.room} required maxLength={100} /></Field><label className="settings-checkbox"><input name="sensitive" type="checkbox" defaultChecked={editing.sensitive} /> Requiere confirmación</label><div className="actions"><button>Guardar</button><button className="secondary" type="button" onClick={() => setEditing(null)}>Cancelar</button></div></form>}
    {error && <p className="error">{error}</p>}</section>;
  return <><h2>Casa</h2>{error && <p className="error">{error}</p>}{!status ? <p className="state">Cargando dispositivos…</p> : !status.connected ? <p className="state error">{status.error || "Home Assistant no está disponible."}</p> : !status.entities.length ? <p className="state">No hay dispositivos permitidos. Un administrador puede añadirlos desde Ajustes.</p> : byRoom.map(([room, entities]) => <section key={room}><h3>{room}</h3><div className="cards home-cards">{entities.map(entity => <article key={entity.id}><label>{entity.display_name}</label><b>{entity.available ? entity.state || "—" : "No disponible"}</b>{entity.consumption !== undefined && <small>{entity.consumption} {entity.consumption_unit}</small>}{["light", "switch", "fan", "input_boolean", "cover", "lock", "alarm_control_panel"].includes(entity.domain) && <div className="actions"><button disabled={busy === entity.id || !entity.available} onClick={() => void control(entity, entity.state === "on" ? "turn_off" : "turn_on")}>{busy === entity.id ? "Enviando…" : entity.state === "on" ? "Apagar" : "Encender"}</button></div>}</article>)}</div></section>)}</>;
}
