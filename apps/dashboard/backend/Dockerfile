FROM python:3.12-slim

WORKDIR /app

# uv for dependency management; gosu to drop root in the entrypoint (see below).
RUN pip install uv \
    && apt-get update \
    && apt-get install -y --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first for layer caching
COPY apps/dashboard/backend/pyproject.toml apps/dashboard/backend/uv.lock* ./

# Install runtime deps (no dev extras)
RUN uv sync --no-dev

# Copy backend source
COPY apps/dashboard/backend/app ./app

# Copy the agent prompts and knowledge vault the backend reads at runtime
COPY plugins/ruflo-stratagent/agents /agents
COPY knowledge-vault /vault

# Operational telemetry core, imported by app/telemetry_bridge.py.
# NOTE: packages/telemetry is NOT independently importable — it depends on
# state -> common -> core (telemetry/events.py: `from state.identifiers import
# new_event_id`). So the whole packages/ tree is copied and put on PYTHONPATH,
# exactly mirroring how a source checkout resolves it (no "works locally,
# breaks in Docker" gap). Only telemetry's closure is ever imported; the rest
# is inert text. That the core cannot be taken a piece at a time is evidence
# for the unify-or-retire question tracked in ADR-008.
COPY packages ./packages
ENV PYTHONPATH=/app/packages

# SQLite lives here, backed by a volume (docker-compose.yml, or a PaaS disk).
# Creating it in the image is what lets a plain Docker NAMED volume inherit the
# right ownership. A managed platform's disk does NOT inherit it — that case is
# handled at runtime by docker-entrypoint.sh.
RUN mkdir -p /app/data

COPY apps/dashboard/backend/docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# The non-root user the app actually runs as. NOTE: no `USER app` here — the
# entrypoint starts as root purely to chown the volume mount, then drops to this
# user via gosu. Setting USER here would make that impossible and the app would
# crash on a root-owned PaaS disk.
RUN useradd -m app && chown -R app /app /agents /vault

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
