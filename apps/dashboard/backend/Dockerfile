FROM python:3.12-slim

WORKDIR /app

# Install uv
RUN pip install uv

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

# SQLite lives here and is backed by a named volume (see docker-compose.yml).
# The directory must exist in the image AND be owned by the runtime user: a
# fresh named volume inherits ownership from the image path it covers, so
# without this the volume mounts as root and the non-root app cannot open the DB.
RUN mkdir -p /app/data

# Non-root user
RUN useradd -m app && chown -R app /app /agents /vault
USER app

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
