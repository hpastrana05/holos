import { useEffect, useState, type FormEvent } from "react";
import { AccountAvatar, avatars, type Account } from "./AccountAvatar";
import { api, Field } from "./shared";
import Home from "./Home";
import Calendar from "./Calendar";
import TelegramSettings from "./TelegramSettings";

type Location = { name: string; latitude: number; longitude: number };

export default function Settings({ token }: { token: string }) {
  const [account, setAccount] = useState<Account | null>(null);
  const [location, setLocation] = useState<Location | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    Promise.all([api("/settings/me", token), api("/settings/weather-location", token)])
      .then(([me, place]) => {
        if (active) {
          setAccount(me);
          setLocation(place);
        }
      })
      .catch((reason: Error) => { if (active) setError(reason.message); });
    return () => { active = false; };
  }, [token]);

  return <>
    <h2>Ajustes</h2>
    {error ? <p className="error" role="alert">{error}</p> : !account || !location ? (
      <p className="state" role="status">Cargando ajustes…</p>
    ) : (
      <div className="settings-grid">
        {account.role === "admin" && <UserSettings token={token} />}
        {account.role === "admin" && <Home token={token} settings />}
        <Calendar token={token} settings />
        <TelegramSettings key={token} token={token} />
        <LocationSettings token={token} location={location} editable={account.role === "admin"} />
        <VoiceSettings />
      </div>
    )}
  </>;
}

function VoiceSettings() {
  const [enabled, setEnabled] = useState(() => localStorage.getItem("holos-speak-replies") === "true");
  return <section><h3>Voz del chat</h3><label className="settings-checkbox"><input type="checkbox" checked={enabled} onChange={event => { const value = event.target.checked; setEnabled(value); localStorage.setItem("holos-speak-replies", String(value)); }} /> Leer las respuestas en voz alta</label><p className="state">La respuesta por voz usa el sintetizador del navegador.</p></section>;
}

function UserSettings({ token }: { token: string }) {
  const [users, setUsers] = useState<Account[] | null>(null);
  const [editing, setEditing] = useState<Account | "new" | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    api("/settings/users", token).then((list: Account[]) => {
      if (active) setUsers(list);
    }).catch((reason: Error) => { if (active) setError(reason.message); });
    return () => { active = false; };
  }, [token]);

  const selected = editing === "new" ? null : editing;
  const save = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const password = String(form.get("password"));
    const pin = String(form.get("pin"));
    const data = {
      name: form.get("name"), email: form.get("email"), role: form.get("role"),
      color: form.get("color"), avatar: form.get("avatar"),
      ...(selected && { is_active: form.has("is_active") }),
      ...(password && { password }),
      ...(pin ? { pin } : form.has("remove_pin") ? { pin: null } : {}),
    };
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const saved: Account = await api(selected ? `/settings/users/${selected.id}` : "/settings/users", token, {
        method: selected ? "PUT" : "POST",
        body: JSON.stringify(data),
      });
      setUsers(previous => selected ? previous!.map(user => user.id === saved.id ? saved : user) : [...(previous || []), saved]);
      setEditing(null);
      setMessage(selected ? "Usuario actualizado." : "Usuario creado.");
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const openEditor = (value: Account | "new") => {
    setError("");
    setMessage("");
    setEditing(value);
  };

  return <section>
    <h3>Usuarios</h3>
    {users ? <ul className="list settings-users">
      {users.map(user => <li key={user.id}>
        <div className="settings-user">
          <AccountAvatar profile={user} />
          <div><b>{user.name}</b><small>{user.email} · {user.role === "admin" ? "Admin" : "Miembro"}{!user.is_active && " · Inactivo"}</small></div>
        </div>
        <button type="button" className="secondary" disabled={busy} onClick={() => openEditor(user)}>Editar</button>
      </li>)}
    </ul> : !error && <p className="state">Cargando usuarios…</p>}
    {users && !editing && <button type="button" onClick={() => openEditor("new")}>Crear usuario</button>}
    {editing && <form key={selected?.id ?? "new"} className="settings-form" onSubmit={save}>
      <h4>{selected ? `Editar a ${selected.name}` : "Nuevo usuario"}</h4>
      <Field label="Nombre"><input name="name" defaultValue={selected?.name} required maxLength={80} /></Field>
      <Field label="Correo o usuario"><input name="email" defaultValue={selected?.email} required maxLength={255} /></Field>
      <Field label={selected ? "Nueva contraseña (opcional)" : "Contraseña"}>
        <input name="password" type="password" autoComplete="new-password" minLength={8} maxLength={128} required={!selected} />
      </Field>
      <Field label="Rol">
        <select name="role" defaultValue={selected?.role || "member"}>
          <option value="member">Miembro</option><option value="admin">Administrador</option>
        </select>
      </Field>
      <Field label="Color"><input name="color" type="color" defaultValue={selected?.color || "#b7a7ff"} /></Field>
      <Field label="Avatar"><select name="avatar" defaultValue={selected?.avatar || "initial"}>
        {Object.entries(avatars).map(([key, label]) => <option value={key} key={key}>{label}</option>)}
      </select></Field>
      <Field label="PIN de pantalla (opcional)" help="De 4 a 8 cifras. Protege el acceso al resumen desde el selector público.">
        <input name="pin" type="password" autoComplete="new-password" inputMode="numeric" pattern="[0-9]{4,8}" maxLength={8} />
      </Field>
      {selected?.has_pin && <label className="settings-checkbox"><input type="checkbox" name="remove_pin" /> Quitar PIN actual</label>}
      {selected && <label className="settings-checkbox"><input type="checkbox" name="is_active" defaultChecked={selected.is_active} /> Usuario activo</label>}
      <div className="actions">
        <button disabled={busy}>{busy ? "Guardando…" : "Guardar usuario"}</button>
        <button className="secondary" type="button" disabled={busy} onClick={() => { setEditing(null); setError(""); }}>Cancelar</button>
      </div>
    </form>}
    {message && <p className="state" role="status">{message}</p>}
    {error && <p className="error" role="alert">{error}</p>}
  </section>;
}

function LocationSettings({ token, location, editable }: { token: string; location: Location; editable: boolean }) {
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return <section>
    <h3>Ubicación del tiempo</h3>
    <form className="settings-form" onSubmit={async (event) => {
      event.preventDefault();
      const form = new FormData(event.currentTarget);
      setBusy(true);
      setMessage("");
      setError("");
      try {
        await api("/settings/weather-location", token, {
          method: "PUT",
          body: JSON.stringify({ name: form.get("name"), latitude: Number(form.get("latitude")), longitude: Number(form.get("longitude")) }),
        });
        setMessage("Ubicación guardada.");
      } catch (reason) {
        setError((reason as Error).message);
      } finally {
        setBusy(false);
      }
    }}>
      <Field label="Nombre"><input name="name" defaultValue={location.name} required maxLength={120} readOnly={!editable} /></Field>
      <Field label="Latitud"><input name="latitude" defaultValue={location.latitude} type="number" min={-90} max={90} step="any" required readOnly={!editable} /></Field>
      <Field label="Longitud"><input name="longitude" defaultValue={location.longitude} type="number" min={-180} max={180} step="any" required readOnly={!editable} /></Field>
      {editable && <button disabled={busy}>{busy ? "Guardando…" : "Guardar ubicación"}</button>}
      {message && <p className="state" role="status">{message}</p>}
      {error && <p className="error" role="alert">{error}</p>}
    </form>
  </section>;
}
