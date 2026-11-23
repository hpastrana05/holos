import { useEffect, useRef, useState, type FormEvent } from "react";
import { api } from "./shared";

type Message = { role: "user" | "assistant"; content: string; actions?: { tool: string; result: string }[] };
const voiceAvailable = () => "SpeechRecognition" in window || "webkitSpeechRecognition" in window;
const label: Record<string, string> = { add_expense: "Gasto añadido", add_income: "Ingreso añadido", add_weight: "Peso añadido", get_finance_summary: "Resumen financiero", get_budget_status: "Presupuesto", get_weight_status: "Estado de peso", get_today_weather: "Tiempo" };

export function ChatPanel({ token }: { token: string }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [listening, setListening] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  const canVoice = typeof window !== "undefined" && voiceAvailable();
  useEffect(() => { end.current?.scrollIntoView({ block: "end" }); }, [messages, busy]);
  const send = async (event?: FormEvent) => {
    event?.preventDefault();
    const message = text.trim(); if (!message || busy) return;
    const history = messages.slice(-12).map(({ role, content }) => ({ role, content }));
    setMessages(previous => [...previous, { role: "user", content: message }]); setText(""); setBusy(true); setError("");
    try {
      const answer = await api("/agent/chat", token, { method: "POST", body: JSON.stringify({ message, history }) });
      setMessages(previous => [...previous, { role: "assistant", content: answer.response, actions: answer.actions }]);
      if (localStorage.getItem("holos-speak-replies") === "true" && "speechSynthesis" in window) {
        speechSynthesis.cancel(); speechSynthesis.speak(new SpeechSynthesisUtterance(answer.response));
      }
    } catch (reason) { setError((reason as Error).message); }
    finally { setBusy(false); }
  };
  const listen = () => {
    const Recognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const recognition = new Recognition(); recognition.lang = "es-ES"; recognition.interimResults = false; recognition.maxAlternatives = 1;
    recognition.onstart = () => setListening(true); recognition.onend = () => setListening(false);
    recognition.onerror = () => { setListening(false); setError("No he podido escuchar el mensaje. Prueba a escribirlo."); };
    recognition.onresult = (event: any) => setText(event.results[0][0].transcript);
    recognition.start();
  };
  return <div className="chat-panel">
    <div className="chat-messages" aria-live="polite">
      {messages.length === 0 && <p className="state">Escribe o dicta una consulta. Puedes registrar gastos, ingresos y pesos, o pedir resúmenes.</p>}
      {messages.map((message, index) => <article className={`chat-message ${message.role}`} key={index}>
        <b>{message.role === "user" ? "Tú" : "Holos"}</b><p>{message.content}</p>
        {message.actions?.map((action, actionIndex) => <div className="chat-action" key={actionIndex}><strong>{label[action.tool] || "Acción"}</strong><span>{action.result}</span></div>)}
      </article>)}
      {busy && <p className="state" role="status">Pensando…</p>}{error && <p className="error" role="alert">{error}</p>}<div ref={end} />
    </div>
    <form className="chat-compose" onSubmit={send}>
      <label className="sr-only" htmlFor="chat-message">Mensaje</label>
      <textarea id="chat-message" value={text} onChange={event => setText(event.target.value)} placeholder="Pregunta a Holos…" rows={2} disabled={busy} />
      {canVoice && <button type="button" className="secondary" onClick={listen} disabled={busy || listening}>{listening ? "Escuchando…" : "Micrófono"}</button>}
      <button disabled={busy || !text.trim()}>{busy ? "Enviando…" : "Enviar"}</button>
    </form>
  </div>;
}

export function ChatFloating({ token }: { token: string }) {
  const [open, setOpen] = useState(false);
  return <><button className="chat-float" type="button" onClick={() => setOpen(true)} aria-label="Abrir chat con Holos">Chat</button>
    {open && <div className="chat-overlay" role="dialog" aria-modal="true" aria-label="Chat con Holos"><section className="chat-dialog"><div className="chat-title"><h2>Chat con Holos</h2><button className="secondary" type="button" onClick={() => setOpen(false)}>Cerrar</button></div><ChatPanel token={token} /></section></div>}
  </>;
}
