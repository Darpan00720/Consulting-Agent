FROM python:3.12-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock* ./

# Install runtime deps (no dev extras)
RUN uv sync --no-dev

# Copy source
COPY . .

# Non-root user
RUN useradd -m app && chown -R app /app
USER app

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
