import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { api } from "./shared";

type Action = { tool: string; result: string };
type Message = { id: number; role: "user" | "assistant"; content: string; createdAt: Date; actions?: Action[] };
type Module = "health" | "finance";
type ChatState = ReturnType<typeof useChat>;
const meta: Record<string, { title: string; icon: string; module?: Module }> = { add_expense: { title: "Gasto añadido", icon: "↘", module: "finance" }, add_income: { title: "Ingreso añadido", icon: "↗", module: "finance" }, add_weight: { title: "Peso añadido", icon: "◒", module: "health" }, get_finance_summary: { title: "Resumen financiero", icon: "€", module: "finance" }, get_budget_status: { title: "Presupuesto", icon: "◔", module: "finance" }, get_weight_status: { title: "Estado de peso", icon: "◒", module: "health" }, get_today_weather: { title: "Tiempo de hoy", icon: "☀" } };
const suggestions = ["Añadir gasto", "Registrar peso", "Resumen del mes", "Tiempo de hoy"];
const supportsVoice = () => typeof window !== "undefined" && ("SpeechRecognition" in window || "webkitSpeechRecognition" in window);
const time = new Intl.DateTimeFormat("es-ES", { hour: "2-digit", minute: "2-digit" });

export function useChat(token: string) {
  const [messages, setMessages] = useState<Message[]>([]), [busy, setBusy] = useState(false), [failure, setFailure] = useState<{ message: string; detail: string } | null>(null);
  const nextId = useRef(1);
  const request = async (content: string, retry = false) => {
    const message = content.trim(); if (!message || busy) return;
    const source = retry && messages.at(-1)?.role === "user" ? messages.slice(0, -1) : messages;
    const history = source.slice(-12).map(({ role, content: item }) => ({ role, content: item }));
    if (!retry) setMessages(previous => [...previous, { id: nextId.current++, role: "user", content: message, createdAt: new Date() }]);
    setBusy(true); setFailure(null);
    try { const answer = await api("/agent/chat", token, { method: "POST", body: JSON.stringify({ message, history }) }); setMessages(previous => [...previous, { id: nextId.current++, role: "assistant", content: answer.response, actions: answer.actions, createdAt: new Date() }]); }
    catch (reason) { setFailure({ message, detail: (reason as Error).message }); }
    finally { setBusy(false); }
  };
  return { messages, busy, failure, request, clear: () => { if ("speechSynthesis" in window) speechSynthesis.cancel(); setMessages([]); setFailure(null); }, retry: () => failure && request(failure.message, true) };
}

function useName(token: string) { const [name, setName] = useState("ahí"); useEffect(() => { let live = true; api("/settings/me", token).then((user: { name: string }) => live && setName(user.name)).catch(() => {}); return () => { live = false; }; }, [token]); return name; }

function ActionCard({ action, onOpenModule }: { action: Action; onOpenModule?: (module: Module) => void }) { const item = meta[action.tool] || { title: "Acción realizada", icon: "✓" }; return <div className={`chat-action action-${action.tool}`}><span className="chat-action-icon" aria-hidden="true">{item.icon}</span><div><strong>{item.title}</strong><span>{action.result}</span></div>{item.module && onOpenModule && <button type="button" className="chat-action-link" onClick={() => onOpenModule(item.module!)}>Abrir</button>}</div>; }

export function ChatPanel({ chat, token, onOpenModule, compact = false }: { chat: ChatState; token: string; onOpenModule?: (module: Module) => void; compact?: boolean }) {
  const [text, setText] = useState(""), [interim, setInterim] = useState(""), [listening, setListening] = useState(false), [voiceNotice, setVoiceNotice] = useState("");
  const end = useRef<HTMLDivElement>(null), input = useRef<HTMLTextAreaElement>(null), recognition = useRef<any>(null); const name = useName(token); const canVoice = supportsVoice(); const spoken = localStorage.getItem("holos-speak-replies") === "true"; const value = `${text}${interim ? `${text ? " " : ""}${interim}` : ""}`;
  useEffect(() => { const area = input.current; if (area) { area.style.height = "auto"; area.style.height = `${Math.min(area.scrollHeight, 144)}px`; } }, [value]);
  useEffect(() => { end.current?.scrollIntoView({ block: "end", behavior: "smooth" }); }, [chat.messages, chat.busy, chat.failure]); useEffect(() => () => recognition.current?.abort(), []);
  useEffect(() => { if (compact) input.current?.focus(); }, [compact]);
  const send = (event?: FormEvent) => { event?.preventDefault(); if (!text.trim() || chat.busy) return; chat.request(text); setText(""); setInterim(""); };
  const listen = () => { if (!canVoice || chat.busy) return; const Recognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition; const item = new Recognition(); recognition.current = item; item.lang = "es-ES"; item.interimResults = true; item.onstart = () => { setListening(true); setVoiceNotice(""); }; item.onend = () => { setListening(false); setInterim(""); }; item.onerror = (event: { error: string }) => { setListening(false); setInterim(""); setVoiceNotice(event.error === "not-allowed" || event.error === "service-not-allowed" ? "Has denegado el permiso del micrófono. Puedes activarlo desde el navegador." : "No he podido escuchar el mensaje. Prueba a escribirlo."); }; item.onresult = (event: any) => { let finalText = "", live = ""; for (let index = event.resultIndex; index < event.results.length; index += 1) event.results[index].isFinal ? finalText += event.results[index][0].transcript : live += event.results[index][0].transcript; if (finalText) setText(previous => `${previous}${previous ? " " : ""}${finalText.trim()}`); setInterim(live.trim()); }; item.start(); };
  const speak = (content: string) => { if ("speechSynthesis" in window) { speechSynthesis.cancel(); speechSynthesis.speak(new SpeechSynthesisUtterance(content)); } };
  return <section className={`chat-panel ${compact ? "chat-panel-compact" : ""}`} aria-label="Conversación con Holos"><div className="chat-messages" aria-live="polite" aria-relevant="additions">
    {!chat.messages.length && !chat.busy && <div className="chat-empty"><span className="chat-orb" aria-hidden="true">✦</span><h3>Hola, {name}</h3><p>¿Qué necesitas registrar o consultar hoy?</p><div className="chat-suggestions">{suggestions.map(item => <button key={item} type="button" className="secondary" onClick={() => { setText(item); input.current?.focus(); }}>{item}</button>)}</div></div>}
    {chat.messages.map(message => <article className={`chat-message ${message.role}`} key={message.id}><div className="chat-bubble"><p>{message.content}</p><time dateTime={message.createdAt.toISOString()}>{time.format(message.createdAt)}</time></div>{message.actions?.map((action, index) => <ActionCard action={action} onOpenModule={onOpenModule} key={index} />)}{message.role === "assistant" && spoken && <button className="chat-speak" type="button" onClick={() => speak(message.content)}>Escuchar</button>}</article>)}
    {chat.busy && <div className="chat-typing" role="status"><span /><span /><span /> Holos está escribiendo…</div>}{chat.failure && <div className="chat-error" role="alert"><div><strong>No se ha podido responder</strong><span>{chat.failure.detail}</span></div><button type="button" onClick={chat.retry} disabled={chat.busy}>Reintentar</button></div>}<div ref={end} />
  </div><form className="chat-compose" onSubmit={send}><label className="sr-only" htmlFor={compact ? "floating-chat-message" : "chat-message"}>Mensaje para Holos</label><textarea ref={input} id={compact ? "floating-chat-message" : "chat-message"} value={value} onChange={event => { setText(event.target.value); setInterim(""); }} onKeyDown={(event: KeyboardEvent<HTMLTextAreaElement>) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); send(); } }} placeholder="Escribe un mensaje…" rows={1} disabled={chat.busy} aria-describedby={voiceNotice ? "voice-notice" : undefined} />{canVoice && <button type="button" className={`chat-mic ${listening ? "is-listening" : ""}`} onClick={listen} disabled={chat.busy || listening}>{listening ? "Escuchando" : "Micrófono"}</button>}<button className="chat-send" disabled={chat.busy || !text.trim()}>{chat.busy ? "…" : "Enviar"}</button>{voiceNotice && <p id="voice-notice" className="chat-voice-notice" role="alert">{voiceNotice}</p>}</form></section>;
}

export function ChatView({ chat, token, onOpenModule }: { chat: ChatState; token: string; onOpenModule: (module: Module) => void }) { return <div className="chat-view"><header className="chat-header"><div><p>Asistente personal</p><h2>Chat con Holos</h2></div><button type="button" className="secondary" onClick={chat.clear} disabled={!chat.messages.length}>Limpiar</button></header><ChatPanel chat={chat} token={token} onOpenModule={onOpenModule} /></div>; }
export function ChatFloating({ chat, token, onOpenModule }: { chat: ChatState; token: string; onOpenModule: (module: Module) => void }) { const [open, setOpen] = useState(false); return <><button className="chat-float" type="button" onClick={() => setOpen(true)} aria-label="Abrir chat con Holos">Chat</button>{open && <div className="chat-overlay" role="presentation" onMouseDown={() => setOpen(false)}><section className="chat-dialog" role="dialog" aria-modal="true" aria-label="Chat con Holos" onMouseDown={event => event.stopPropagation()}><header className="chat-title"><div><p>Holos</p><h2>¿En qué te ayudo?</h2></div><button className="secondary" type="button" onClick={() => setOpen(false)}>Cerrar</button></header><ChatPanel chat={chat} token={token} onOpenModule={onOpenModule} compact /></section></div>}</>; }
