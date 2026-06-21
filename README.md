# AI Customer Support Refund Agent

An AI agent that **processes or denies e-commerce refunds** — and holds a written refund
policy against pleading, argument, social engineering, and prompt injection. It pairs a
customer-facing **storefront + support chat** with an operator-facing **reasoning dashboard**
that makes every decision auditable, and runs **zero-config** end to end.

## What it does

- A customer opens the **storefront**, browses their orders, and clicks **Report an issue** on one.
- The agent runs a guided support conversation: it asks **which order** and **what's wrong** with
  on-screen buttons (not free text), gathers a reason, troubleshoots quality issues, and for
  claims it can't verify it **requires a photo** — the model looks at the image and checks it's a
  genuine product-and-receipt shot, not a stock/online picture.
- It then **approves, denies, or escalates** strictly per policy — and the outcome is
  **re-validated in code**, so the LLM never gets the last word on a hard rule.
- Every run is recorded as a step-by-step **trace** (tool I/O, tokens, cost, latency, retries, the
  exact prompt) in the **Reasoning** dashboard, and exported as **OpenTelemetry** spans.

## Quick start (zero config)

```bash
# add your key to a root .env:  ANTHROPIC_API_KEY=sk-ant-...
docker compose up --build
```

| | URL |
|---|---|
| App (storefront + chat + admin) | http://localhost:5173 |
| API health | http://localhost:8000/api/health |
| Jaeger — OpenTelemetry trace waterfall | http://localhost:16686 |

The CRM auto-seeds on first start (15 customers, 30 orders with histories). No other setup.

## Architecture — clean UI / API / orchestration separation

| Layer | Stack | Responsibility |
|---|---|---|
| **Frontend** | React + Vite + Tailwind | Storefront, support chat (drawer), Reasoning + Orders admin. Talks only to the REST API. |
| **API** | FastAPI | `/api/chat`, `/api/customers`, `/api/orders`, `/api/traces[/{id}]`, `/api/policy`, `/api/health` |
| **Agent** | LangGraph + Anthropic SDK | State machine (agent ↔ tools loop) driving Claude `claude-sonnet-4-6` |
| **Policy** | `policy_engine.py` + `refund_policy.md` | Deterministic rules (the source of truth) + the human-readable policy |
| **Data** | SQLite | CRM (customers, orders), per-order claim log, persisted traces |

## How it holds the line (defense in depth)

The conversation belongs to the LLM; the **decision belongs to code.**

1. **Input guardrail** — deterministic scan for manipulation / jailbreak patterns; flags add a per-turn security note.
2. **Hardened system prompt** — strict workflow, confidentiality, explicitly anti-rubber-stamping.
3. **Deterministic policy engine** — `issue_refund` re-evaluates every request against the rules and refuses anything ineligible, no matter what the model "decided".
4. **Output guardrails** — block fabricated "refund processed" claims, and scrub internal rule IDs / policy text so the customer never sees them.
5. **Evidence + abuse signals** — photo evidence for unverifiable claims, and a persisted per-order claim log for reason-shopping / serial-return detection.

20+ prompt-injection, jailbreak, and social-engineering techniques were red-teamed — transcripts in `chats/`.

## The refund policy

- **Deny:** R1 ownership · R2 delivered-only · R3 final-sale · R4 already-refunded · R5 30-day window · R8 14-day change-of-mind window.
- **Escalate:** R6 over $500 · R9 ≥2 prior refunds · R10 late defect/damage (15–30 days) · R11 reason-shopping (re-claimed under a new reason) · R12 unverifiable claim from an account with history · R13 unverifiable claim with no photo.
- **Approve** only after a valid reason has been gathered (R7).

## Observability

- **Reasoning dashboard** — a flight-recorder timeline per run: tool I/O, tokens in→out, cost, latency, prompt-cache savings, the **exact prompt** sent, and a copyable `trace_id`.
- **Structured JSON logs** to stdout, keyed by `trace_id` — grep one run end to end.
- **OpenTelemetry** spans (GenAI semantic conventions: `gen_ai.request.model`, token usage, …) exported over OTLP to **Jaeger**.
- **Failure handling** — failed runs are *persisted* (debuggable, not a silent 500) and degrade gracefully; a built-in **fault injector** (demo only) shows a retried/failed step on demand.

## Tests

```bash
cd backend
python -m venv .venv && .venv/Scripts/activate     # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q                                # 83 passing, no API calls
python -m pytest tests/test_resilience.py -q       # adversarial suite (needs ANTHROPIC_API_KEY; live)
```

## Local dev (without Docker)

- Backend: `cd backend && uvicorn app.main:app --reload`
- Frontend: `cd frontend && npm install && npm run dev` (proxies `/api` → `http://localhost:8000`)

## Deployment

DigitalOcean **App Platform** spec in `.do/app.yaml`: backend service at `/api`, frontend static
site at `/`, optional Jaeger at `/jaeger`. Auto-deploys on push to `main`. `ANTHROPIC_API_KEY` is an
encrypted secret; fault injection and OpenTelemetry are **env-gated** (off by default — opt in with
`ENABLE_FAULT_INJECTION=1` / `OTEL_ENABLED=1`).

## What I'd add before production

OpenTelemetry **metric** dashboards + alerting (cost / error-rate / approval-rate) · PII redaction
and retention on stored prompts and photos · **idempotency keys on refunds** (a retry must never
double-pay) · a durable session/trace store (sessions are in-memory today) · per-account cost/rate
budgets + a circuit breaker · real customer authentication · an offline eval harness for
policy-adherence regression.
