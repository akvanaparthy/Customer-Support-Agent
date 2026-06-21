# AI Customer Support Refund Agent

An AI agent that approves, denies, or escalates e-commerce refunds, holding a written
refund policy under pleading and prompt-injection. Customer chat UI + admin reasoning dashboard.

## Quick start (zero config)

1. `cp .env.example .env` and paste your `ANTHROPIC_API_KEY`.
2. `docker compose up --build`
3. Open the app: **http://localhost:5173** — API health: **http://localhost:8000/api/health**

The CRM database auto-seeds on first start (15 customers with order histories). No other setup.

## Architecture

- **Frontend** — React + Vite + Tailwind SPA (Chat + Admin). Talks only to the REST API.
- **API** — FastAPI. `POST /api/chat`, `GET /api/traces[/{id}]`, `GET /api/customers`, `GET /api/policy`, `GET /api/health`.
- **Agent** — LangGraph state machine driving Claude (`claude-sonnet-4-6`) via the Anthropic SDK.
- **Data** — SQLite CRM + `refund_policy.md` (human-readable) + `policy_engine.py` (deterministic enforcement).

**Resilience (defense in depth):** the policy is enforced in code. `issue_refund` re-validates
every request against `policy_engine.py`, so no amount of pleading or prompt-injection can
produce an unauthorized refund. The LLM runs the conversation; it never gets the last word on a hard rule.

## Running the tests

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate   # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -v                       # unit suite (no API calls): 32 passing
python -m pytest tests/test_resilience.py -v   # adversarial suite (needs ANTHROPIC_API_KEY; live API)
```

## Local dev (without Docker)

- Backend: `cd backend && uvicorn app.main:app --reload`
- Frontend: `cd frontend && npm install && npm run dev` (proxies `/api` to `http://localhost:8000`)

## What I'd add before production

Real authentication & customer identity verification; persistent session store; response
streaming; rate limiting; PII redaction in trace logs; an offline eval harness for
policy-adherence regression; structured observability/alerting; and a human-in-the-loop
queue for escalations.
