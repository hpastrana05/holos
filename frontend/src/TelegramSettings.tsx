import { useEffect, useState } from "react";
import { api } from "./shared";

export default function TelegramSettings({ token }: { token: string }) {
  const [linked, setLinked] = useState<boolean | null>(null);
  const [code, setCode] = useState<{ value: string; expires: number } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    if (busy) return;
    const refresh = async () => {
      try {
        const status = await api("/settings/telegram", token);
        if (!active) return;
        setLinked(status.linked);
        if (status.linked) setCode(null);
      } catch (failure) {
        if (active) setError((failure as Error).message);
      }
    };
    const timer = code ? window.setInterval(refresh, 4000) : undefined;
    const expiry = code ? window.setTimeout(() => setCode(null), Math.max(0, code.expires - Date.now())) : undefined;
    void refresh();
    window.addEventListener("focus", refresh);
    return () => {
      active = false;
      window.removeEventListener("focus", refresh);
      window.clearInterval(timer);
      window.clearTimeout(expiry);
    };
  }, [token, code, busy]);

  async function changeLink() {
    setBusy(true);
    setError("");
    try {
      if (linked) {
        await api("/settings/telegram", token, { method: "DELETE" });
        setLinked(false);
        setCode(null);
      } else {
        const result = await api("/settings/telegram/code", token, { method: "POST" });
        setCode({ value: result.code, expires: Date.now() + result.expires_in * 1000 });
      }
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return <section>
    <h3>Telegram</h3>
    {linked !== null && <>
      <p className="state">{linked ? "Vinculado" : "Sin vincular"}</p>
      <button type="button" disabled={busy} onClick={changeLink}>
        {linked ? "Desvincular Telegram" : code ? "Generar otro código" : "Vincular Telegram"}
      </button>
    </>}
    {linked === null && !error && <p className="state">Cargando estado…</p>}
    {code && <div>
      <p>Envía este comando en el chat privado con tu bot. El código caduca en 10 minutos.</p>
      <code>/start {code.value}</code>
    </div>}
    {error && <p role="alert">{error}</p>}
  </section>;
}
