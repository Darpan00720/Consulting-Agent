# Security Policy

## Supported versions

StratAgent is pre-1.0 (`0.1.0-rc2`, *Ready for Limited Beta*). Security fixes are
applied to the latest `main`; there are no back-ported release branches yet.

| Version | Supported |
|---|---|
| `main` / latest `0.1.0-rc*` | ✅ |
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

StratAgent runs locally inside Claude Code plus a `uv`-managed Python
environment. There is **no server, no auth surface, and no secrets are required**
by the core system. Relevant properties:

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

### Known trust assumptions (not vulnerabilities, but operator-relevant)
- The **content** an operator pastes into `/solve-case` is processed by the LLM;
  do not paste secrets or regulated data you would not send to your model provider.
- Prompt-injection resistance depends on the model + optional Ruflo guardrails
  (`ruflo-aidefence`); treat ingested third-party documents as untrusted.

See the [RC1 Engineering Audit — Security Review](docs/reviews/RC1-Engineering-Audit.md)
for the reviewed findings.
