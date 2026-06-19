export interface Order {
  id: number;
  item_name: string;
  category: string;
  amount: number;
  status: string;
  order_date: string;
  delivered_date: string | null;
  is_final_sale: boolean;
  is_refunded: boolean;
}

export interface Customer {
  id: number;
  name: string;
  email: string;
  tier: string;
  orders: Order[];
}

export type Decision = "approved" | "denied" | "escalated" | null;

export interface ChatResponse {
  reply: string;
  decision: Decision;
  trace_id: string;
  session_id: string;
}

export interface PromptContext {
  system: string;
  messages: { role: string; content: string }[];
}

export interface TraceStep {
  type: string;
  name: string;
  input: unknown;
  output: unknown;
  tokens_in: number;
  tokens_out: number;
  cache_read?: number;
  cache_write?: number;
  latency_ms: number;
  cost_usd: number;
  status: string;
  context?: PromptContext | null;
}

export interface TraceSummary {
  trace_id: string;
  customer_name: string | null;
  timestamp: string;
  user_message: string;
  decision: Decision;
  total_tokens_in: number;
  total_tokens_out: number;
  total_cost_usd: number;
  total_latency_ms: number;
  step_count: number;
}

export interface Trace extends TraceSummary {
  session_id: string;
  customer_id: number | null;
  steps: TraceStep[];
}

export interface AdminOrder {
  id: number;
  customer_id: number;
  customer_name: string;
  customer_email: string;
  item_name: string;
  category: string;
  amount: number;
  status: string;
  order_date: string;
  delivered_date: string | null;
  is_final_sale: number;
  is_refunded: number;
  refund_date: string | null;
}
