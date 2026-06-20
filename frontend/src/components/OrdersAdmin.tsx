import { useEffect, useState } from "react";
import { api } from "../api";
import type { AdminOrder } from "../types";

const STATUSES = ["processing", "shipped", "delivered", "cancelled"];

const statusText: Record<string, string> = {
  delivered: "text-approved",
  shipped: "text-agent",
  processing: "text-escalated",
  cancelled: "text-muted",
};

type Patch = Partial<{ status: string; is_refunded: boolean; is_final_sale: boolean }>;

function Toggle({ on, onChange, disabled }: { on: boolean; onChange: (v: boolean) => void; disabled?: boolean }) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => onChange(!on)}
      aria-pressed={on}
      className={`relative inline-flex h-5 w-9 items-center rounded-full transition disabled:opacity-50 ${on ? "bg-agent" : "bg-line"}`}
    >
      <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition ${on ? "translate-x-4" : "translate-x-0.5"}`} />
    </button>
  );
}

const td = "border-b border-line px-4 py-2.5";

export default function OrdersAdmin() {
  const [orders, setOrders] = useState<AdminOrder[]>([]);
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = () => api.orders().then(setOrders).catch(() => setOrders([]));
  useEffect(() => {
    load();
  }, []);

  async function patch(id: number, p: Patch) {
    setBusyId(id);
    try {
      const updated = await api.updateOrder(id, p);
      setOrders((os) => os.map((o) => (o.id === id ? updated : o)));
    } catch {
      load();
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="mx-auto h-full max-w-6xl px-4 py-4">
      <div className="flex h-full animate-fade-in flex-col overflow-hidden rounded-2xl border border-line bg-surface shadow-sm">
        <div className="flex items-center justify-between border-b border-line px-5 py-3">
          <div>
            <div className="font-display text-sm font-semibold text-ink">Orders</div>
            <div className="text-xs text-muted">Change status or flip a flag to set up a scenario for the agent.</div>
          </div>
          <span className="font-mono text-xs text-muted tabular">{orders.length} orders</span>
        </div>
        <div className="min-h-0 flex-1 overflow-auto">
          <table className="w-full border-separate border-spacing-0 text-sm">
            <thead className="sticky top-0 z-10 bg-paper">
              <tr className="text-left font-mono text-[10px] uppercase tracking-wide text-muted">
                {["Order", "Customer", "Item", "Amount", "Status", "Delivered", "Final sale", "Refunded"].map((h) => (
                  <th key={h} className="border-b border-line px-4 py-2.5 font-medium">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {orders.map((o) => (
                <tr key={o.id} className={`transition hover:bg-paper ${busyId === o.id ? "opacity-50" : ""}`}>
                  <td className={`${td} font-mono text-ink tabular`}>#{o.id}</td>
                  <td className={`${td} text-ink`}>
                    {o.customer_name} <span className="font-mono text-xs text-muted">#{o.customer_id}</span>
                  </td>
                  <td className={`${td} text-ink`}>{o.item_name}</td>
                  <td className={`${td} font-mono text-ink tabular`}>${o.amount.toFixed(2)}</td>
                  <td className={td}>
                    <select
                      value={o.status}
                      disabled={busyId === o.id}
                      onChange={(e) => patch(o.id, { status: e.target.value })}
                      className={`rounded-lg border border-line bg-surface px-2 py-1 text-xs font-medium capitalize transition focus:border-agent focus:outline-none ${statusText[o.status] ?? "text-ink"}`}
                    >
                      {STATUSES.map((s) => (
                        <option key={s} value={s} className="text-ink">
                          {s}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className={`${td} font-mono text-xs text-muted tabular`}>{o.delivered_date ?? "—"}</td>
                  <td className={td}>
                    <Toggle on={!!o.is_final_sale} disabled={busyId === o.id} onChange={(v) => patch(o.id, { is_final_sale: v })} />
                  </td>
                  <td className={td}>
                    <Toggle on={!!o.is_refunded} disabled={busyId === o.id} onChange={(v) => patch(o.id, { is_refunded: v })} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
