import type { AdminOrder, ChatResponse, Customer, Trace, TraceSummary } from "./types";

async function get<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${url}`);
  return r.json() as Promise<T>;
}

export const api = {
  customers: () => get<{ customers: Customer[] }>("/api/customers").then((d) => d.customers),
  policy: () => get<{ policy: string }>("/api/policy").then((d) => d.policy),
  traces: () => get<{ traces: TraceSummary[] }>("/api/traces").then((d) => d.traces),
  trace: (id: string) => get<Trace>(`/api/traces/${id}`),
  chat: async (sessionId: string, customerId: number, message: string): Promise<ChatResponse> => {
    const r = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, customer_id: customerId, message }),
    });
    if (!r.ok) throw new Error(`chat ${r.status}`);
    return r.json() as Promise<ChatResponse>;
  },
  orders: () => get<{ orders: AdminOrder[] }>("/api/orders").then((d) => d.orders),
  updateOrder: async (
    id: number,
    patch: Partial<{ status: string; is_refunded: boolean; is_final_sale: boolean }>,
  ): Promise<AdminOrder> => {
    const r = await fetch(`/api/orders/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    });
    if (!r.ok) throw new Error(`update ${r.status}`);
    return r.json() as Promise<AdminOrder>;
  },
};
