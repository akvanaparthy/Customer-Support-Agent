import { useEffect, useState, type Dispatch, type SetStateAction } from "react";
import ChatWindow from "./ChatWindow";
import type { ChatMsg } from "../App";
import type { Customer, Order } from "../types";

const statusChip: Record<string, string> = {
  delivered: "bg-approved-soft text-approved",
  shipped: "bg-agent-soft text-agent",
  processing: "bg-escalated-soft text-escalated",
  cancelled: "bg-line text-muted",
  escalated: "bg-escalated-soft text-escalated",
  refunded: "bg-agent-soft text-agent",
};

function initials(name: string) {
  return name.split(" ").map((w) => w[0]).slice(0, 2).join("").toUpperCase();
}

function OrderCard({ order, onClick }: { order: Order; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="group flex flex-col rounded-2xl border border-line bg-surface p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-agent/40 hover:shadow-md"
    >
      <div className="flex items-center justify-between">
        <span className="font-mono text-xs text-muted tabular">#{order.id}</span>
        <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${statusChip[order.status] ?? "bg-line text-muted"}`}>
          {order.status}
        </span>
      </div>
      <div className="mt-2 font-display text-sm font-semibold text-ink">{order.item_name}</div>
      <div className="mt-0.5 text-xs text-muted">{order.category}</div>
      <div className="mt-3 flex items-center justify-between">
        <span className="font-mono text-sm font-semibold text-ink tabular">${order.amount.toFixed(2)}</span>
        <span className="flex items-center gap-1.5">
          {order.is_final_sale && <span className="text-[10px] font-semibold uppercase tracking-wide text-muted">final sale</span>}
          {order.is_refunded && <span className="text-[10px] font-semibold uppercase tracking-wide text-agent">refunded</span>}
          <span className="text-muted transition group-hover:translate-x-0.5 group-hover:text-agent">→</span>
        </span>
      </div>
    </button>
  );
}

function Row({ label, value, mono, strong }: { label: string; value: string; mono?: boolean; strong?: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-muted">{label}</span>
      <span className={`text-ink ${mono ? "font-mono tabular " : ""}${strong ? "font-semibold" : ""}`}>{value}</span>
    </div>
  );
}

function OrderDetail({ order, onBack, onReport }: { order: Order; onBack: () => void; onReport: () => void }) {
  return (
    <div className="mt-6 animate-fade-up">
      <button onClick={onBack} className="text-sm text-muted transition hover:text-ink">
        ← Back to orders
      </button>
      <div className="mt-3 max-w-xl overflow-hidden rounded-2xl border border-line bg-surface shadow-sm">
        <div className="flex items-start justify-between border-b border-line px-5 py-4">
          <div>
            <div className="font-mono text-xs text-muted tabular">Order #{order.id}</div>
            <div className="mt-0.5 font-display text-lg font-semibold text-ink">{order.item_name}</div>
          </div>
          <span className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide ${statusChip[order.status] ?? "bg-line text-muted"}`}>
            {order.status}
          </span>
        </div>
        <div className="space-y-2 px-5 py-4 text-sm">
          <Row label="Category" value={order.category} />
          <Row label="Order date" value={order.order_date} mono />
          <Row label="Delivered" value={order.delivered_date ?? "—"} mono />
          <div className="my-2 border-t border-line" />
          <Row label="Subtotal" value={`$${order.amount.toFixed(2)}`} mono />
          <Row label="Total" value={`$${order.amount.toFixed(2)}`} mono strong />
          <div className="my-2 border-t border-line" />
          <Row label="Final sale" value={order.is_final_sale ? "Yes" : "No"} />
          <Row label="Refunded" value={order.is_refunded ? "Yes" : "No"} />
        </div>
        <div className="border-t border-line px-5 py-4">
          <button
            onClick={onReport}
            className="w-full rounded-xl bg-agent px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-agent-hover"
          >
            Report an issue
          </button>
        </div>
      </div>
    </div>
  );
}

export default function StorefrontView({
  customers,
  sessionId,
  onViewTrace,
  onNewChat,
  messages,
  setMessages,
  customerId,
  setCustomerId,
}: {
  customers: Customer[];
  sessionId: string;
  onViewTrace: (traceId: string) => void;
  onNewChat: () => void;
  messages: ChatMsg[];
  setMessages: Dispatch<SetStateAction<ChatMsg[]>>;
  customerId: number | null;
  setCustomerId: Dispatch<SetStateAction<number | null>>;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [selectedOrderId, setSelectedOrderId] = useState<number | null>(null);
  const [chatOpen, setChatOpen] = useState(false);
  const [seed, setSeed] = useState<{ text: string; nonce: number } | null>(null);

  useEffect(() => {
    if (customers.length && customerId === null) setCustomerId(customers[0].id);
  }, [customers, customerId, setCustomerId]);

  const customer = customers.find((c) => c.id === customerId);
  const orders = customer?.orders ?? [];
  const selectedOrder = orders.find((o) => o.id === selectedOrderId) ?? null;

  function pickCustomer(id: number) {
    setCustomerId(id);
    onNewChat();
    setSelectedOrderId(null);
    setChatOpen(false);
    setMenuOpen(false);
  }

  function openChat() {
    // resume the current conversation; the drawer's "New chat" button starts a fresh one
    setChatOpen(true);
  }

  function reportIssue(o: Order) {
    onNewChat();
    setSeed({ text: `I'd like to report an issue with order #${o.id} (${o.item_name}).`, nonce: Date.now() });
    setChatOpen(true);
  }

  return (
    <div className="relative h-full overflow-hidden">
      <div className="h-full overflow-y-auto">
        <div className="mx-auto max-w-4xl px-4 py-6">
          {/* account header */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="relative">
              <button
                onClick={() => setMenuOpen((o) => !o)}
                className="flex items-center gap-3 rounded-2xl border border-line bg-surface px-3 py-2.5 text-left shadow-sm transition hover:border-agent/40"
              >
                <span className="flex h-10 w-10 items-center justify-center rounded-full bg-agent text-sm font-semibold text-white">
                  {customer ? initials(customer.name) : "—"}
                </span>
                <span className="leading-tight">
                  <span className="block font-display text-sm font-semibold text-ink">{customer?.name ?? "Select a customer"}</span>
                  <span className="block text-xs text-muted">{customer?.email ?? "—"}</span>
                </span>
                {customer && (
                  <span className="ml-1 rounded-full border border-line px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted">
                    {customer.tier} member
                  </span>
                )}
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-muted">
                  <path d="M6 9l6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>

              {menuOpen && (
                <>
                  <button className="fixed inset-0 z-40 cursor-default" aria-label="Close menu" onClick={() => setMenuOpen(false)} />
                  <div className="absolute left-0 top-full z-50 mt-2 max-h-80 w-72 overflow-y-auto rounded-2xl border border-line bg-surface p-1.5 shadow-xl">
                    <div className="px-2.5 py-1.5 text-[10px] font-semibold uppercase tracking-wide text-muted">Switch customer (demo)</div>
                    {customers.map((c) => (
                      <button
                        key={c.id}
                        onClick={() => pickCustomer(c.id)}
                        className={`flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2 text-left transition hover:bg-paper ${
                          c.id === customerId ? "bg-agent-soft/60" : ""
                        }`}
                      >
                        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-paper text-[10px] font-semibold text-ink">
                          {initials(c.name)}
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm font-medium text-ink">{c.name}</span>
                          <span className="block font-mono text-[10px] text-muted tabular">#{c.id} · {c.tier}</span>
                        </span>
                        {c.id === customerId && <span className="text-xs text-agent">●</span>}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>

            <button
              onClick={openChat}
              className="flex items-center gap-2 rounded-xl bg-agent px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:-translate-y-0.5 hover:bg-agent-hover"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H8l-5 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
              Chat with us
            </button>
          </div>

          {/* orders / detail */}
          {selectedOrder ? (
            <OrderDetail order={selectedOrder} onBack={() => setSelectedOrderId(null)} onReport={() => reportIssue(selectedOrder)} />
          ) : (
            <div className="mt-8">
              <div className="flex items-baseline justify-between">
                <h2 className="font-display text-base font-semibold text-ink">My orders</h2>
                <span className="font-mono text-xs text-muted tabular">{orders.length} orders</span>
              </div>
              {orders.length === 0 ? (
                <p className="mt-4 text-sm text-muted">No orders on this account yet.</p>
              ) : (
                <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {orders.map((o) => (
                    <OrderCard key={o.id} order={o} onClick={() => setSelectedOrderId(o.id)} />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* chat drawer */}
      {chatOpen && (
        <button
          aria-label="Close chat"
          onClick={() => setChatOpen(false)}
          className="absolute inset-0 z-20 cursor-default bg-ink/20 backdrop-blur-sm animate-fade-in"
        />
      )}
      <div
        className={`absolute inset-y-0 right-0 z-30 w-full max-w-md transform border-l border-line shadow-2xl transition-transform duration-300 ${
          chatOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <ChatWindow
          customers={customers}
          sessionId={sessionId}
          onViewTrace={onViewTrace}
          onNewChat={onNewChat}
          onClose={() => setChatOpen(false)}
          messages={messages}
          setMessages={setMessages}
          customerId={customerId}
          seed={seed}
          onSeedConsumed={() => setSeed(null)}
        />
      </div>
    </div>
  );
}
