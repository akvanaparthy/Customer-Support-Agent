import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api } from "../api";
import type { Customer, Decision } from "../types";

interface Msg {
  role: "user" | "agent";
  text: string;
  decision?: Decision;
  traceId?: string;
}

const badge: Record<string, string> = {
  approved: "bg-green-100 text-green-700",
  denied: "bg-red-100 text-red-700",
  escalated: "bg-amber-100 text-amber-700",
};

export default function ChatWindow({
  customers,
  sessionId,
  onViewTrace,
}: {
  customers: Customer[];
  sessionId: string;
  onViewTrace: (traceId: string) => void;
}) {
  const [customerId, setCustomerId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (customers.length && customerId === null) setCustomerId(customers[0].id);
  }, [customers, customerId]);

  async function send() {
    if (!input.trim() || customerId === null || busy) return;
    const text = input.trim();
    setInput("");
    setMessages((m) => [...m, { role: "user", text }]);
    setBusy(true);
    try {
      const res = await api.chat(sessionId, customerId, text);
      setMessages((m) => [
        ...m,
        { role: "agent", text: res.reply, decision: res.decision, traceId: res.trace_id },
      ]);
    } catch (e) {
      setMessages((m) => [...m, { role: "agent", text: `Error: ${String(e)}` }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex h-[calc(100vh-8rem)] max-w-2xl flex-col">
      <div className="mb-3 flex items-center gap-2 text-sm">
        <span className="text-slate-500">Logged in as</span>
        <select
          className="rounded border px-2 py-1"
          value={customerId ?? ""}
          onChange={(e) => {
            setCustomerId(Number(e.target.value));
            setMessages([]);
          }}
        >
          {customers.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name} (#{c.id})
            </option>
          ))}
        </select>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto rounded border bg-white p-4">
        {messages.length === 0 && (
          <p className="text-sm text-slate-400">
            Ask about an order or request a refund. Try to talk the agent into breaking policy — it won't.
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "text-right" : "text-left"}>
            {m.role === "user" ? (
              <div className="inline-block whitespace-pre-wrap rounded-lg bg-slate-800 px-3 py-2 text-sm text-white">
                {m.text}
              </div>
            ) : (
              <div className="md inline-block max-w-full rounded-lg bg-slate-100 px-3 py-2 text-left text-sm">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.text}</ReactMarkdown>
              </div>
            )}
            {m.role === "agent" && (m.decision || m.traceId) && (
              <div className="mt-1 flex items-center gap-2 text-xs">
                {m.decision && (
                  <span className={`rounded px-2 py-0.5 ${badge[m.decision] ?? "bg-slate-100"}`}>
                    {m.decision}
                  </span>
                )}
                {m.traceId && (
                  <button className="text-blue-600 hover:underline" onClick={() => onViewTrace(m.traceId!)}>
                    view reasoning →
                  </button>
                )}
              </div>
            )}
          </div>
        ))}
        {busy && <p className="text-sm text-slate-400">thinking…</p>}
      </div>

      <div className="mt-3 flex gap-2">
        <input
          className="flex-1 rounded border px-3 py-2 text-sm"
          placeholder="Type a message…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
        />
        <button
          className="rounded bg-slate-800 px-4 py-2 text-sm text-white disabled:opacity-50"
          onClick={send}
          disabled={busy}
        >
          Send
        </button>
      </div>
    </div>
  );
}
