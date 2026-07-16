# StratAgent Dashboard

**Live at [stratagent.up.railway.app](https://stratagent.up.railway.app)** —
that's how to use StratAgent. Everything in this file is internal/operator
documentation for the app itself (self-hosting a dev copy, configuration,
API reference), not a second way for visitors to run it.

A web app for running StratAgent consulting engagements from the browser.
**No accounts, no signup**: paste a business problem (and paste in charts or
screenshots if you have them), watch the engagement run live (classify → scope →
plan → frame → issue tree → 5 specialist analysts → reconcile → reviewer →
challenger → report), and get an executive-ready markdown report.

Runs on a **multi-provider free tier** (Gemini, Cerebras, OpenRouter, GitHub
Models, Cloudflare) with automatic failover — or on **your own key** from any
supported provider.

```
apps/dashboard/
  backend/    FastAPI + OpenAI-compatible provider chain  (port 8000)
  frontend/   Next.js 15 + React 19                       (port 3000)
```

The backend loads the **same agent prompts** the Claude Code plugin uses
(`plugins/ruflo-stratagent/agents/*.md`) and the governed framework vault
index (`knowledge-vault/frameworks/`), so dashboard engagements run the same
consultants as `/solve-case`. Governance is mandatory: reviewer and challenger
always run before the report-writer (ADR-006).

### Governance rework loop (MBB-grade reconciliation)

The reviewer's verdict is **acted on**, not just recorded. If it returns
`needs_rework` (e.g. the financial and operations analysts assumed different
values for the same figure), the engine re-dispatches the *implicated*
analysts — each now sees the reviewer's specific issues **and** every other
analyst's findings — so they reconcile onto one factbase, and the reviewer
runs again. This repeats up to `STRATAGENT_MAX_REWORK` times (default 1).

- Both gates clear → **final executive-ready report**.
- Gates don't clear after rework → an **honest interim status report**,
  clearly flagged "not a final recommendation" with a reconciliation list.
  This is the platform refusing to ship contradictory numbers — by design.

The two gate verdicts and any reconciliation passes are persisted on the
engagement and shown as badges above the report (so history is faithful too).

Failures surface as plain, actionable sentences (billing, invalid key, rate
limit, …) — never the raw SDK JSON error.

## Quick start

### 1. Try it with zero setup (no API key, no signup)

Mock mode runs the **entire** pipeline with canned outputs — instant, free, and
enough to see the whole lifecycle and UI:

```bash
cd apps/dashboard
STRATAGENT_MOCK=1 docker compose up --build
# → http://localhost:3000
```

### 2. Run real engagements (free provider keys)

Create `apps/dashboard/.env` with **at least one** provider key — every key is
optional and any subset works; providers without a key are simply skipped:

```bash
# apps/dashboard/.env
GEMINI_API_KEY=AIza...          # https://aistudio.google.com/apikey  (best free tier)
CEREBRAS_API_KEY=csk-...        # https://cloud.cerebras.ai          (handles big prompts)
OPENROUTER_API_KEY=sk-or-...    # https://openrouter.ai/keys
```

```bash
cd apps/dashboard
docker compose up --build       # → http://localhost:3000
```

A full engagement takes ~5–7 minutes on free keys. If every provider hits its
rate limit, the engagement **pauses and auto-resumes** from its last completed
step — you never lose work or need to re-run.

> **Scaling tip.** Free quota is metered per *project* (Gemini) or per
> *organization* (Cerebras), so several independent keys multiply capacity.
> List them comma-separated — each becomes its own paced chain entry:
> `GEMINI_API_KEY=key_project1,key_project2,key_project3`
> Keys from the *same* project/org share one quota and will only cause 429s.

### 3. Or bring your own key (no server keys needed)

Paste any supported key into the UI — Anthropic, OpenAI, OpenRouter, Cerebras,
Groq, or Google. The whole run uses that provider's top model, bypasses the
free-tier quota, and the key **never leaves the request** (never stored, never
logged).

### Local dev without Docker

```bash
cd apps/dashboard/backend && uv run --extra dev pytest   # 67 tests, mock mode
cd apps/dashboard/backend && uv run uvicorn app.main:app --port 8000
cd apps/dashboard/frontend && npm install && npm run dev
```

## Configuration (environment variables)

**Provider keys** — any subset; each may be a comma-separated list (see the
scaling tip above). The chain order is Gemini → Cerebras → OpenRouter → GitHub
Models → Cloudflare, with automatic failover.

| Variable | Purpose |
|---|---|
| `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google AI Studio. Best free tier; reads pasted charts. |
| `CEREBRAS_API_KEY` | Cerebras. 30k TPM — serves the large reconcile/report prompts. |
| `OPENROUTER_API_KEY` | OpenRouter free models. |
| `GITHUB_MODELS_TOKEN` / `GITHUB_TOKEN` | GitHub PAT with the `models: read` scope. |
| `CLOUDFLARE_ACCOUNT_ID` + `CLOUDFLARE_API_TOKEN` | Workers AI — **both** required (the id is in the URL). |

**Behaviour**

| Variable | Default | Purpose |
|---|---|---|
| `STRATAGENT_MOCK` | off | `1` = canned outputs, no API calls |
| `STRATAGENT_DAILY_QUOTA` | `5` | Free-tier engagements per client id / 24 h |
| `STRATAGENT_MAX_TOKENS` | `4096` | Per-agent output budget |
| `STRATAGENT_REPORT_MAX_TOKENS` | `8192` | Report-writer output budget |
| `STRATAGENT_MAX_REWORK` | `1` | Reviewer→reconcile retries before an interim report |
| `STRATAGENT_MAX_CONCURRENT` | `8` | Engagements running at once (server-wide) |
| `STRATAGENT_DB` | `backend/dashboard.db` | SQLite path (Docker: `/app/data/dashboard.db`) |
| `STRATAGENT_CORS_ORIGINS` | `http://localhost:3000` | Allowed frontend origins |
| `NEXT_PUBLIC_API_URL` (frontend) | `http://localhost:8000` | Backend base URL |

**Auto-resume** (rate-limit resilience)

| Variable | Default | Purpose |
|---|---|---|
| `STRATAGENT_AUTO_RESUME` | `1` | Kill switch for pause-and-resume |
| `STRATAGENT_MAX_AUTO_RESUMES` | `6` | Give up after this many automatic retries |
| `STRATAGENT_MIN_RESUME_DELAY` / `STRATAGENT_MAX_RESUME_DELAY` | `20` / `900` | Backoff bounds (seconds, exponential + jittered) |

**Telemetry** (operational; separate from the domain event log)

| Variable | Default | Purpose |
|---|---|---|
| `STRATAGENT_TELEMETRY` | `1` | Kill switch |
| `STRATAGENT_TELEMETRY_DIR` | next to the DB | One JSONL trace per engagement |
| `STRATAGENT_TELEMETRY_SAMPLE` | `1.0` | Sample rate, 0.0–1.0 |

Read traces with the core's analytics CLI:

```bash
uv run python scripts/engagement_telemetry.py --all --root <telemetry-dir>
uv run python scripts/engagement_telemetry.py --all --root <dir> --quality
```

## API

| Endpoint | Method | Description |
|---|---|---|
| `/api/engagements` | POST | Start an engagement (202; runs async). Body: `case_prompt`, optional `api_key` (BYOK — used for the run, never stored) |
| `/api/engagements` | GET | List the caller's engagements |
| `/api/engagements/{id}` | GET | Status + final report |
| `/api/engagements/{id}/events` | GET | **SSE** — replays history, then streams live phase events |
| `/api/health` | GET | Liveness + model + mock/free-tier flags |

Identity is an anonymous, browser-generated id sent as `X-Client-Id`
(`?client=` for SSE). No passwords, no emails, no sessions.

SSE event types: `engagement_started`, `phase_started`, `phase_completed`
(carries the agent's markdown output and duration), `analyst_started`,
`analyst_completed`, `engagement_completed` (carries the report),
`engagement_failed`.

## Bring your own key (BYOK)

There is no signup. The **API key** page stores the user's Anthropic key in
**browser localStorage only**; it is sent with each run request, handed to the
Claude client, and never persisted server-side (a test pins this).

- BYOK runs have **no daily limit** (the spend is the user's own).
- If the operator sets a server `ANTHROPIC_API_KEY`, keyless visitors get a
  small free tier (`STRATAGENT_DAILY_QUOTA` per browser per 24 h).
- With neither, the API returns 402 asking for a key.

The UI follows the **Trust & Authority** design system generated by the
[ui-ux-pro-max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill)
skill: professional navy + blue CTA, IBM Plex Sans, WCAG AA contrast, SVG
icons, visible focus states, and `prefers-reduced-motion` support.

## Cost & runtime

A full engagement makes ~11 Claude calls (default `claude-opus-4-8`,
adaptive thinking). Typical runtime is 5–15 minutes and a few dollars per
engagement; set `STRATAGENT_MODEL=claude-sonnet-5` to trade some quality for
~40% lower cost.

## Tests

```bash
cd apps/dashboard/backend
uv run --extra dev pytest -q     # 11 tests, all in mock mode — no API key needed
```

## Production notes (before going public)

This is a beta-grade foundation. Before real public exposure:

- Put the backend behind HTTPS and a reverse proxy; move SQLite → Postgres.
- The anonymous client id is spoofable (it's client-generated); add real
  rate limiting (IP-based) or optional accounts if the free tier is abused.
- Add billing (Stripe) keyed to the per-user quota.
- Run engagements in a task queue (e.g. arq/Celery) instead of in-process
  asyncio tasks so they survive server restarts.
- Sanitize/limit case prompts and add abuse monitoring.
