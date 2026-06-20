import { useEffect, useState, type ReactNode } from "react";
import { api } from "../api";
import type { Trace, TraceStep, TraceSummary } from "../types";

const decisionPill: Record<string, string> = {
  approved: "bg-approved-soft text-approved",
  denied: "bg-denied-soft text-denied",
  escalated: "bg-escalated-soft text-escalated",
};

function nodeClass(s: TraceStep): string {
  if (s.status === "error") return "node-error";
  if (s.status === "flagged" || s.type.includes("guardrail")) return "node-guardrail";
  if (s.status === "retried" || s.type === "retry") return "node-retry";
  if (s.type === "llm_call") return "node-agent";
  if (s.type === "tool_call") return "node-tool";
  return "";
}

function Stat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="rounded-xl border border-line bg-paper px-3 py-2">
      <div className="text-[10px] font-medium uppercase tracking-wide text-muted">{label}</div>
      <div className="mt-0.5 font-mono text-sm text-ink tabular">{value}</div>
    </div>
  );
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

  const cacheRead = trace ? trace.steps.reduce((a, s) => a + (s.cache_read ?? 0), 0) : 0;
  const cacheWrite = trace ? trace.steps.reduce((a, s) => a + (s.cache_write ?? 0), 0) : 0;

  return (
    <div className="mx-auto grid h-full max-w-6xl grid-cols-1 gap-4 px-4 py-4 md:grid-cols-[20rem_1fr]">
      {/* runs list */}
      <aside className="flex min-h-0 flex-col overflow-hidden rounded-2xl border border-line bg-surface shadow-sm">
        <div className="flex items-center justify-between border-b border-line px-4 py-3">
          <div className="font-display text-sm font-semibold text-ink">Recent runs</div>
          <div className="flex items-center gap-1.5 text-[11px] text-muted">
            <span className="h-1.5 w-1.5 rounded-full bg-approved" /> live
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-2">
          {summaries.length === 0 && <p className="p-3 text-sm text-muted">No runs yet. Send a message in Chat.</p>}
          {summaries.map((s, i) => (
            <button
              key={s.trace_id}
              onClick={() => setSelectedId(s.trace_id)}
              style={{ animationDelay: `${Math.min(i, 8) * 30}ms` }}
              className={`mb-1.5 block w-full animate-fade-up rounded-xl border px-3 py-2.5 text-left transition ${
                selectedId === s.trace_id ? "border-agent/40 bg-agent-soft/60" : "border-transparent hover:border-line hover:bg-paper"
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="truncate text-xs font-semibold text-ink">{s.customer_name ?? "—"}</span>
                {s.decision && (
                  <span className={`rounded-full px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wide ${decisionPill[s.decision] ?? "bg-line text-muted"}`}>
                    {s.decision}
                  </span>
                )}
              </div>
              <div className="mt-0.5 truncate text-xs text-muted">{s.user_message}</div>
              <div className="mt-1 font-mono text-[10px] text-muted tabular">
                {s.step_count} steps · {s.total_tokens_in + s.total_tokens_out} tok · ${s.total_cost_usd.toFixed(4)} · {s.total_latency_ms}ms
              </div>
            </button>
          ))}
        </div>
      </aside>

      {/* trace detail */}
      <section className="min-h-0 overflow-y-auto rounded-2xl border border-line bg-surface shadow-sm">
        {!trace ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center text-muted">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-paper text-agent">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 12h4l3 8 4-16 3 8h4" />
              </svg>
            </div>
            <p className="font-display text-base font-semibold text-ink">Replay the agent's reasoning</p>
            <p className="max-w-xs text-sm">Pick a run to see every step — guardrails, tool calls, tokens, latency, and cost.</p>
          </div>
        ) : (
          <div className="p-5">
            <div className="flex flex-wrap items-center gap-3">
              <span className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide ${decisionPill[trace.decision ?? ""] ?? "bg-line text-muted"}`}>
                {trace.decision ?? "no decision"}
              </span>
              <span className="text-sm font-medium text-ink">{trace.customer_name}</span>
            </div>
            <p className="mt-3 border-l-2 border-agent/30 pl-3 text-sm italic text-ink">“{trace.user_message}”</p>

            <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
              <Stat label="steps" value={trace.step_count} />
              <Stat label="tokens" value={trace.total_tokens_in + trace.total_tokens_out} />
              <Stat label="cost" value={`$${trace.total_cost_usd.toFixed(5)}`} />
              <Stat label="latency" value={`${trace.total_latency_ms}ms`} />
            </div>
            {(cacheRead > 0 || cacheWrite > 0) && (
              <div className="mt-2 font-mono text-[11px] text-muted tabular">
                cache · <span className="font-semibold text-approved">{cacheRead}</span> read · {cacheWrite} written
                <span className="text-muted/70"> — reads bill at 0.1×</span>
              </div>
            )}

            <ol className="mt-5">
              {trace.steps.map((s, i) => (
                <li
                  key={i}
                  style={{ animationDelay: `${Math.min(i, 10) * 45}ms` }}
                  className="trace-step flex animate-fade-up gap-3 pb-4"
                >
                  <div className="rail">
                    <span className={`node ${nodeClass(s)}`} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
                      <span className="text-sm text-ink">
                        <span className="font-semibold">{s.type.replace(/_/g, " ")}</span>
                        <span className="text-muted"> · {s.name}</span>
                      </span>
                      <span className="font-mono text-[11px] text-muted tabular">
                        {s.latency_ms}ms
                        {s.tokens_in + s.tokens_out > 0 && ` · ${s.tokens_in}→${s.tokens_out} tok`}
                        {(s.cache_read ?? 0) > 0 && ` · ${s.cache_read} cached`}
                        {s.tokens_in + s.tokens_out > 0 && ` · $${s.cost_usd.toFixed(6)}`}
                      </span>
                    </div>
                    {s.input != null && (
                      <pre className="mt-1 overflow-x-auto whitespace-pre-wrap break-words font-mono text-[11px] text-muted">
                        in: {typeof s.input === "string" ? s.input : JSON.stringify(s.input)}
                      </pre>
                    )}
                    {s.output != null && (
                      <pre className="mt-0.5 overflow-x-auto whitespace-pre-wrap break-words font-mono text-[11px] text-ink/80">
                        out: {typeof s.output === "string" ? s.output : JSON.stringify(s.output)}
                      </pre>
                    )}
                    {s.context && (
                      <details className="mt-1.5">
                        <summary className="cursor-pointer font-mono text-[11px] text-agent transition hover:underline">
                          ▸ exact prompt sent ({s.context.messages.length} msgs + system)
                        </summary>
                        <div className="mt-2 space-y-2 rounded-xl border border-line bg-paper p-3">
                          <div>
                            <div className="text-[10px] font-semibold uppercase tracking-wide text-muted">system</div>
                            <pre className="whitespace-pre-wrap break-words font-mono text-[11px] text-muted">{s.context.system}</pre>
                          </div>
                          {s.context.messages.map((m, j) => (
                            <div key={j}>
                              <div className="text-[10px] font-semibold uppercase tracking-wide text-muted">
                                {j + 1}. {m.role}
                              </div>
                              <pre className="whitespace-pre-wrap break-words font-mono text-[11px] text-ink/80">{m.content}</pre>
                            </div>
                          ))}
                        </div>
                      </details>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          </div>
        )}
      </section>
    </div>
  );
}
