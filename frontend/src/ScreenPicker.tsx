import { useEffect, useState } from "react";
import { AccountAvatar, type Profile } from "./AccountAvatar";

export default function ScreenPicker({ onSession }: { onSession: (token: string) => void }) {
  const [profiles, setProfiles] = useState<Profile[] | null>(null);
  const [selected, setSelected] = useState<Profile | null>(null);
  const [pin, setPin] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/screen/users", { cache: "no-store", credentials: "omit", signal: controller.signal })
      .then(response => {
        if (!response.ok) throw new Error();
        return response.json();
      })
      .then((list: Profile[]) => setProfiles(list))
      .catch(() => { if (!controller.signal.aborted) setError("No se pudo cargar el selector."); });
    return () => controller.abort();
  }, [retry]);

  const start = async (profile: Profile, value?: string) => {
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/screen/session", {
        method: "POST", credentials: "omit", cache: "no-store",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: profile.id, pin: value }),
      });
      const data = await response.json();
      if (response.ok) {
        onSession(data.access_token);
        return;
      }
      if (data.detail?.code === "pin_required") {
        setSelected(profile);
        setPin("");
      } else {
        setError(data.detail?.message || (typeof data.detail === "string" ? data.detail : "No se pudo iniciar la sesión."));
      }
    } catch {
      setError("No se pudo iniciar la sesión.");
    } finally {
      setBusy(false);
    }
  };

  return <section className="screen-setup">
    <h1>{selected ? selected.name : "Elige un usuario"}</h1>
    {selected ? <form onSubmit={event => { event.preventDefault(); void start(selected, pin); }}>
      <label className="field">PIN de pantalla
        <input type="password" value={pin} onChange={event => setPin(event.target.value)}
          inputMode="numeric" pattern="[0-9]{4,8}" maxLength={8} required autoFocus />
      </label>
      <div className="actions">
        <button disabled={busy}>Continuar</button>
        <button type="button" className="secondary" disabled={busy} onClick={() => {
          setSelected(null); setPin(""); setError("");
        }}>Volver</button>
      </div>
    </form> : profiles ? (
      profiles.length ? <div className="screen-profiles">
        {profiles.map(profile => <button className="secondary" key={profile.id} type="button" disabled={busy}
          onClick={() => void start(profile)}>
          <AccountAvatar profile={profile} /> <span>{profile.name}</span>
        </button>)}
      </div> : <p className="state">No hay usuarios activos.</p>
    ) : error ? <button type="button" onClick={() => { setError(""); setRetry(value => value + 1); }}>Reintentar</button>
      : <p className="state" role="status">Cargando usuarios…</p>}
    {error && <p className="error" role="alert">{error}</p>}
  </section>;
}
