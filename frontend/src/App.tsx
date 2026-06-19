import { useEffect, useState } from "react";
import { api } from "./api";
import ChatWindow from "./components/ChatWindow";
import AdminDashboard from "./components/AdminDashboard";
import OrdersAdmin from "./components/OrdersAdmin";
import type { Customer } from "./types";

type Tab = "chat" | "admin" | "orders";

export default function App() {
  const [tab, setTab] = useState<Tab>("chat");
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [focusTraceId, setFocusTraceId] = useState<string | null>(null);
  const [sessionId] = useState(() => crypto.randomUUID());

  useEffect(() => {
    api.customers().then(setCustomers).catch(() => setCustomers([]));
  }, []);

  function viewTrace(id: string) {
    setFocusTraceId(id);
    setTab("admin");
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      <header className="flex items-center gap-4 border-b bg-white px-6 py-3">
        <h1 className="font-semibold">🛒 Refund Support Agent</h1>
        <nav className="flex gap-2 text-sm">
          {(["chat", "admin", "orders"] as Tab[]).map((t) => (
            <button
              key={t}
              className={`rounded px-3 py-1 capitalize ${tab === t ? "bg-slate-800 text-white" : "hover:bg-slate-100"}`}
              onClick={() => setTab(t)}
            >
              {t}
            </button>
          ))}
        </nav>
      </header>
      <main className="p-6">
        {tab === "chat" ? (
          <ChatWindow customers={customers} sessionId={sessionId} onViewTrace={viewTrace} />
        ) : tab === "admin" ? (
          <AdminDashboard focusTraceId={focusTraceId} />
        ) : (
          <OrdersAdmin />
        )}
      </main>
    </div>
  );
}
