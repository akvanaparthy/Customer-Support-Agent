import { useEffect, useState } from "react";
import { api } from "../api";
import type { AdminOrder } from "../types";

const STATUSES = ["processing", "shipped", "delivered", "cancelled"];

type Patch = Partial<{ status: string; is_refunded: boolean; is_final_sale: boolean }>;

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
    <div className="h-[calc(100vh-8rem)] overflow-auto rounded border bg-white">
      <table className="w-full text-xs">
        <thead className="sticky top-0 bg-slate-100 text-left">
          <tr>
            <th className="px-3 py-2">Order</th>
            <th className="px-3 py-2">Customer</th>
            <th className="px-3 py-2">Item</th>
            <th className="px-3 py-2">Amount</th>
            <th className="px-3 py-2">Status</th>
            <th className="px-3 py-2">Delivered</th>
            <th className="px-3 py-2">Final sale</th>
            <th className="px-3 py-2">Refunded</th>
          </tr>
        </thead>
        <tbody>
          {orders.map((o) => (
            <tr key={o.id} className={`border-t ${busyId === o.id ? "opacity-50" : ""}`}>
              <td className="px-3 py-2 font-medium">#{o.id}</td>
              <td className="px-3 py-2">
                {o.customer_name} <span className="text-slate-400">#{o.customer_id}</span>
              </td>
              <td className="px-3 py-2">{o.item_name}</td>
              <td className="px-3 py-2">${o.amount.toFixed(2)}</td>
              <td className="px-3 py-2">
                <select
                  className="rounded border px-1 py-0.5"
                  value={o.status}
                  disabled={busyId === o.id}
                  onChange={(e) => patch(o.id, { status: e.target.value })}
                >
                  {STATUSES.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </td>
              <td className="px-3 py-2 text-slate-500">{o.delivered_date ?? "—"}</td>
              <td className="px-3 py-2">
                <input
                  type="checkbox"
                  checked={!!o.is_final_sale}
                  disabled={busyId === o.id}
                  onChange={(e) => patch(o.id, { is_final_sale: e.target.checked })}
                />
              </td>
              <td className="px-3 py-2">
                <input
                  type="checkbox"
                  checked={!!o.is_refunded}
                  disabled={busyId === o.id}
                  onChange={(e) => patch(o.id, { is_refunded: e.target.checked })}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
