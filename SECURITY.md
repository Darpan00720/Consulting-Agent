# Security Policy

## Supported versions

StratAgent is pre-1.0 (`1.0.0-beta.1`, *Ready for Limited Beta*). Security fixes
are applied to the latest `main`; there are no back-ported release branches yet.

| Version | Supported |
|---|---|
| `main` / latest `1.0.0-beta.*` | ✅ |
| older pre-releases | ❌ |

## Reporting a vulnerability

**Do not open a public issue for a security vulnerability.**

Email **darpan20071992@gmail.com** with:
- a description and impact assessment,
- reproduction steps (and a minimal engagement/prompt if relevant),
- affected version/commit.

You will receive an acknowledgement, and we will work on a fix and coordinated
disclosure. Please give a reasonable window before public disclosure.

## Security model & scope

StratAgent ships in two forms with different threat models:

1. **The Claude Code plugin + core** run locally inside Claude Code plus a
   `uv`-managed Python environment. There is **no server, no auth surface, and
   no secrets are required** by the core system.
2. **The web dashboard** (`apps/dashboard/`) is a public FastAPI + Next.js
   server. See *Dashboard-specific properties* below.

Relevant properties of the local core:

- **No external data sources by default.** The knowledge vault contains no live
  feeds; an [Evidence Provider (ADR-007)](docs/architecture/ADR-007-Evidence-Providers.md)
  is the *only* sanctioned way to add one, and its credentials are the provider's
  responsibility — **never commit credentials**.
- **YAML is parsed with `yaml.safe_load`** (no arbitrary object construction).
- **Subprocess calls use list form** (no `shell=True`); user input does not flow
  into a shell.
- **Telemetry is privacy-bounded** — no engagement content (report prose, client
  facts) is persisted; metadata is redacted and size-capped
  ([Retention & Privacy](docs/observability/Retention-Privacy.md)).
- **Filesystem writes** are confined to `engagements/`, `telemetry/`, and (for
  the curator) `knowledge-vault/`; path building is escape-guarded.

### Dashboard-specific properties (`apps/dashboard/`)
- **BYOK keys are never persisted or logged.** A user-supplied API key travels
  in the request body, is used for that run only, and is never written to disk;
  only a boolean `used_byok` flag is stored (pinned by
  `test_api_key_never_persisted` and `test_used_byok_flag_stores_no_key_material`).
- **Pasted images are never persisted** — they are held in memory for the run
  and dropped; a pasted chart may contain client data (pinned by
  `test_pasted_images_never_persisted`).
- **Server provider keys** live only in `apps/dashboard/.env` (git-ignored) or
  the container environment — never in tracked files.
- **Request size is bounded** — per-image and aggregate payload caps prevent a
  single request from pinning memory; a server-wide concurrency cap
  (`STRATAGENT_MAX_CONCURRENT`) bounds simultaneous engagements.

### Known trust assumptions (not vulnerabilities, but operator-relevant)
- The **content** an operator pastes into `/solve-case` or the dashboard is
  processed by the LLM; do not paste secrets or regulated data you would not
  send to your model provider.
- Prompt-injection resistance depends on the model + optional Ruflo guardrails
  (`ruflo-aidefence`); treat ingested third-party documents as untrusted.
- **The dashboard's anonymous `X-Client-Id` is caller-asserted, not
  authenticated.** The per-client daily free-tier quota is therefore a
  courtesy limit, **not an abuse control** — a determined caller can reset it by
  changing the id. This is an accepted limitation of the no-signup design for
  beta; a public deployment expecting abuse should front the service with
  IP-based rate limiting or a real identity layer. BYOK runs bypass the quota by
  design (the user pays their own provider).

See the [RC1 Engineering Audit — Security Review](docs/reviews/RC1-Engineering-Audit.md)
for the reviewed findings.
