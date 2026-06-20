import { useEffect, useRef, useState, type Dispatch, type SetStateAction } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api } from "../api";
import type { ChatMsg } from "../App";
import type { Customer } from "../types";

const badge: Record<string, string> = {
  approved: "bg-approved-soft text-approved",
  denied: "bg-denied-soft text-denied",
  escalated: "bg-escalated-soft text-escalated",
};

export default function ChatWindow({
  customers,
  sessionId,
  onViewTrace,
  onNewChat,
  onClose,
  messages,
  setMessages,
  customerId,
  seed,
  onSeedConsumed,
}: {
  customers: Customer[];
  sessionId: string;
  onViewTrace: (traceId: string) => void;
  onNewChat: () => void;
  onClose: () => void;
  messages: ChatMsg[];
  setMessages: Dispatch<SetStateAction<ChatMsg[]>>;
  customerId: number | null;
  seed: { text: string; nonce: number } | null;
  onSeedConsumed: () => void;
}) {
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const sentSeed = useRef<number | null>(null);

  const current = customers.find((c) => c.id === customerId);
  const lastMsg = messages[messages.length - 1];
  const pendingOptions = lastMsg?.role === "agent" ? lastMsg.options : undefined;
  const locked = !!pendingOptions?.length;

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, busy]);

  async function send(text?: string) {
    const msg = (text ?? input).trim();
    if (!msg || customerId === null || busy) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", text: msg }]);
    setBusy(true);
    try {
      const res = await api.chat(sessionId, customerId, msg);
      setMessages((m) => [
        ...m,
        { role: "agent", text: res.reply, decision: res.decision, traceId: res.trace_id, options: res.options ?? undefined },
      ]);
    } catch (e) {
      setMessages((m) => [...m, { role: "agent", text: `I couldn't reach the support agent just now. ${String(e)}` }]);
    } finally {
      setBusy(false);
    }
  }

  // auto-send a seed message (e.g. from "Report an issue") once per nonce
  useEffect(() => {
    if (seed && seed.nonce !== sentSeed.current && customerId !== null) {
      sentSeed.current = seed.nonce;
      void send(seed.text);
      onSeedConsumed();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seed, customerId]);

  return (
    <div className="flex h-full flex-col bg-surface">
      {/* header */}
      <div className="flex items-center justify-between border-b border-line px-4 py-3">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-agent text-white">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M12 2l1.7 6.1L20 10l-6.3 1.9L12 18l-1.7-6.1L4 10l6.3-1.9z" />
            </svg>
          </div>
          <div className="leading-tight">
            <div className="font-display text-sm font-semibold text-ink">Support</div>
            <div className="text-[11px] text-muted">{current ? `Chatting as ${current.name}` : "—"}</div>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => onNewChat()}
            title="New chat"
            aria-label="New chat"
            className="rounded-lg p-2 text-muted transition hover:bg-paper hover:text-agent"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 5v14M5 12h14" />
            </svg>
          </button>
          <button
            onClick={() => onClose()}
            title="Close"
            aria-label="Close chat"
            className="rounded-lg p-2 text-muted transition hover:bg-paper hover:text-ink"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
        </div>
      </div>

      {/* conversation */}
      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto bg-paper/40 p-4">
        {messages.length === 0 && !busy && (
          <div className="flex h-full animate-fade-in flex-col items-center justify-center gap-3 px-4 text-center">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-agent-soft text-agent">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H8l-5 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
            </div>
            <p className="font-display text-base font-semibold text-ink">How can I help?</p>
            <p className="text-sm text-muted">Ask about an order or a refund, and I'll take a look.</p>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`flex animate-fade-up ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={m.role === "user" ? "max-w-[85%]" : "max-w-[92%]"}>
              {m.role === "user" ? (
                <div className="rounded-2xl rounded-br-md bg-agent px-4 py-2.5 text-sm text-white shadow-sm">{m.text}</div>
              ) : (
                <div className="md rounded-2xl rounded-bl-md border border-line bg-surface px-4 py-3 text-sm leading-relaxed text-ink shadow-sm">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.text}</ReactMarkdown>
                </div>
              )}
              {m.role === "agent" && (m.decision || m.traceId) && (
                <div className="mt-1.5 flex items-center gap-2 pl-1">
                  {m.decision && (
                    <span
                      className={`animate-pop rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
                        badge[m.decision] ?? "bg-line text-muted"
                      }`}
                    >
                      {m.decision}
                    </span>
                  )}
                  {m.traceId && (
                    <button
                      onClick={() => onViewTrace(m.traceId!)}
                      className="text-xs font-medium text-agent transition hover:underline"
                    >
                      view reasoning →
                    </button>
                  )}
                </div>
              )}
              {m.role === "agent" && m.options && i === messages.length - 1 && (
                <div className="mt-2 flex flex-wrap gap-2">
                  {m.options.map((opt) => (
                    <button
                      key={opt}
                      onClick={() => send(opt)}
                      disabled={busy}
                      className="rounded-xl border border-agent/30 bg-agent-soft px-3 py-2 text-xs font-medium text-agent transition hover:-translate-y-0.5 hover:bg-agent hover:text-white disabled:opacity-50"
                    >
                      {opt}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {busy && (
          <div className="flex animate-fade-in justify-start">
            <div className="dots rounded-2xl rounded-bl-md border border-line bg-surface px-4 py-3.5 text-muted shadow-sm">
              <span />
              <span />
              <span />
            </div>
          </div>
        )}
      </div>

      {/* composer */}
      <div className="border-t border-line p-3">
        <div className="flex items-center gap-2 rounded-2xl border border-line bg-surface p-1.5 transition focus-within:border-agent focus-within:ring-4 focus-within:ring-agent/10">
          <input
            className="flex-1 bg-transparent px-3 py-2 text-sm text-ink placeholder:text-muted focus:outline-none disabled:cursor-not-allowed"
            placeholder={locked ? "Choose an option above to continue…" : "Message support…"}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            disabled={customerId === null || locked}
          />
          <button
            onClick={() => send()}
            disabled={busy || locked || !input.trim()}
            className="flex h-9 w-9 items-center justify-center rounded-xl bg-agent text-white transition hover:bg-agent-hover disabled:opacity-40"
            aria-label="Send message"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M5 12h14M13 6l6 6-6 6" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
