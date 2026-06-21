import { useEffect, useState } from "react";
import { api } from "./api";
import StorefrontView from "./components/StorefrontView";
import AdminDashboard from "./components/AdminDashboard";
import OrdersAdmin from "./components/OrdersAdmin";
import type { Customer, Decision } from "./types";

type Tab = "chat" | "admin" | "orders";

const TABS: { id: Tab; label: string }[] = [
  { id: "chat", label: "Storefront" },
  { id: "admin", label: "Reasoning" },
  { id: "orders", label: "Orders" },
];

export interface ChatMsg {
  role: "user" | "agent";
  text: string;
  decision?: Decision;
  traceId?: string;
  options?: string[];
  awaiting_photo?: boolean;
  image?: string; // data URL thumbnail for an uploaded photo (user messages)
}

export default function App() {
  const [tab, setTab] = useState<Tab>("chat");
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [focusTraceId, setFocusTraceId] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState(() => crypto.randomUUID());
  // chat state lives here so switching tabs never drops the conversation
  const [chatMessages, setChatMessages] = useState<ChatMsg[]>([]);
  const [chatCustomerId, setChatCustomerId] = useState<number | null>(null);

  useEffect(() => {
    api.customers().then(setCustomers).catch(() => setCustomers([]));
  }, []);

  function viewTrace(id: string) {
    setFocusTraceId(id);
    setTab("admin");
  }

  // a new chat = a fresh backend session (so it doesn't inherit the prior transcript)
  function newChat() {
    setSessionId(crypto.randomUUID());
    setChatMessages([]);
  }

  return (
    <div className="flex h-full flex-col bg-paper text-ink">
      <header className="flex items-center justify-between border-b border-line bg-surface/85 px-5 py-3 backdrop-blur">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-agent text-white shadow-sm">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M12 2l1.7 6.1L20 10l-6.3 1.9L12 18l-1.7-6.1L4 10l6.3-1.9z" />
            </svg>
          </div>
          <div className="leading-tight">
            <div className="font-display text-sm font-bold tracking-tight text-ink">Refund Agent</div>
            <div className="text-[10px] text-muted">policy enforced in code</div>
          </div>
        </div>
        <nav className="flex items-center gap-1 rounded-xl border border-line bg-paper p-1">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`rounded-lg px-3.5 py-1.5 text-sm font-medium transition ${
                tab === t.id ? "bg-surface text-ink shadow-sm" : "text-muted hover:text-ink"
              }`}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      <main className="min-h-0 flex-1">
        <div key={tab} className="h-full animate-fade-in">
          {tab === "chat" && (
            <StorefrontView
              customers={customers}
              sessionId={sessionId}
              onViewTrace={viewTrace}
              onNewChat={newChat}
              messages={chatMessages}
              setMessages={setChatMessages}
              customerId={chatCustomerId}
              setCustomerId={setChatCustomerId}
            />
          )}
          {tab === "admin" && <AdminDashboard focusTraceId={focusTraceId} />}
          {tab === "orders" && <OrdersAdmin />}
        </div>
      </main>
    </div>
  );
}
