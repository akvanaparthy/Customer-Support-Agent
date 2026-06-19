import { useEffect, useState } from "react";
import { api } from "../api";
import type { Trace, TraceStep, TraceSummary } from "../types";

const badge: Record<string, string> = {
  approved: "bg-green-100 text-green-700",
  denied: "bg-red-100 text-red-700",
  escalated: "bg-amber-100 text-amber-700",
};

function stepColor(s: TraceStep): string {
  if (s.status === "error") return "border-red-300 bg-red-50";
  if (s.status === "flagged" || s.type === "input_guardrail" || s.type === "output_guardrail")
    return "border-purple-300 bg-purple-50";
  if (s.status === "retried" || s.type === "retry") return "border-amber-300 bg-amber-50";
  return "border-slate-200 bg-white";
}

export default function AdminDashboard({ focusTraceId }: { focusTraceId: string | null }) {
  const [summaries, setSummaries] = useState<TraceSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(focusTraceId);
  const [trace, setTrace] = useState<Trace | null>(null);

  useEffect(() => {
    const load = () => api.traces().then(setSummaries).catch(() => {});
    load();
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (focusTraceId) setSelectedId(focusTraceId);
  }, [focusTraceId]);

  useEffect(() => {
    if (selectedId) api.trace(selectedId).then(setTrace).catch(() => setTrace(null));
  }, [selectedId]);

  return (
    <div className="grid h-[calc(100vh-8rem)] grid-cols-[20rem_1fr] gap-4">
      <aside className="overflow-y-auto rounded border bg-white">
        <div className="border-b px-3 py-2 text-sm font-medium">Recent runs</div>
        {summaries.length === 0 && <p className="p-3 text-sm text-slate-400">No runs yet.</p>}
        {summaries.map((s) => (
          <button
            key={s.trace_id}
            onClick={() => setSelectedId(s.trace_id)}
            className={`block w-full border-b px-3 py-2 text-left text-xs hover:bg-slate-50 ${
              selectedId === s.trace_id ? "bg-slate-100" : ""
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="truncate">{s.customer_name ?? "—"}</span>
              {s.decision && (
                <span className={`rounded px-1.5 ${badge[s.decision] ?? "bg-slate-100"}`}>{s.decision}</span>
              )}
            </div>
            <div className="truncate text-slate-500">{s.user_message}</div>
            <div className="text-slate-400">
              {s.step_count} steps · {s.total_tokens_in + s.total_tokens_out} tok · $
              {s.total_cost_usd.toFixed(5)} · {s.total_latency_ms} ms
            </div>
          </button>
        ))}
      </aside>

      <section className="overflow-y-auto rounded border bg-white p-4">
        {!trace ? (
          <p className="text-sm text-slate-400">Select a run to inspect its reasoning trace.</p>
        ) : (
          <>
            <div className="mb-3 flex flex-wrap gap-3 rounded bg-slate-50 p-3 text-xs">
              <span>Decision: <b>{trace.decision ?? "—"}</b></span>
              <span>Steps: <b>{trace.step_count}</b></span>
              <span>Tokens: <b>{trace.total_tokens_in + trace.total_tokens_out}</b></span>
              <span>Cost: <b>${trace.total_cost_usd.toFixed(5)}</b></span>
              <span>Latency: <b>{trace.total_latency_ms} ms</b></span>
            </div>
            <ol className="space-y-2">
              {trace.steps.map((s, i) => (
                <li key={i} className={`rounded border p-3 text-xs ${stepColor(s)}`}>
                  <div className="mb-1 flex items-center justify-between font-medium">
                    <span>{i + 1}. {s.type} · {s.name}</span>
                    <span className="text-slate-500">
                      {s.latency_ms} ms
                      {s.tokens_in + s.tokens_out > 0 &&
                        ` · ${s.tokens_in}/${s.tokens_out} tok · $${s.cost_usd.toFixed(6)}`}
                    </span>
                  </div>
                  {s.input != null && (
                    <pre className="overflow-x-auto whitespace-pre-wrap break-words text-slate-600">
                      in: {typeof s.input === "string" ? s.input : JSON.stringify(s.input)}
                    </pre>
                  )}
                  {s.output != null && (
                    <pre className="overflow-x-auto whitespace-pre-wrap break-words text-slate-700">
                      out: {typeof s.output === "string" ? s.output : JSON.stringify(s.output)}
                    </pre>
                  )}
                  {s.context && (
                    <details className="mt-2">
                      <summary className="cursor-pointer select-none text-slate-500">
                        ▸ view exact prompt sent to the model ({s.context.messages.length} messages + system)
                      </summary>
                      <div className="mt-2 space-y-2 rounded bg-slate-50 p-2">
                        <div>
                          <div className="text-[10px] font-semibold uppercase text-slate-400">system</div>
                          <pre className="whitespace-pre-wrap break-words text-slate-600">{s.context.system}</pre>
                        </div>
                        {s.context.messages.map((m, j) => (
                          <div key={j}>
                            <div className="text-[10px] font-semibold uppercase text-slate-400">
                              {j + 1}. {m.role}
                            </div>
                            <pre className="whitespace-pre-wrap break-words text-slate-700">{m.content}</pre>
                          </div>
                        ))}
                      </div>
                    </details>
                  )}
                </li>
              ))}
            </ol>
          </>
        )}
      </section>
    </div>
  );
}
