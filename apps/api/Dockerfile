# Multi-stage Python 3.12 API image
FROM python:3.12-slim AS base

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency resolution
RUN pip install uv==0.5.18 --no-cache-dir

WORKDIR /app

# ── Dependencies stage ───────────────────────────────────────────────────────
FROM base AS deps
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev

# ── Final stage ──────────────────────────────────────────────────────────────
FROM base AS final
WORKDIR /app

# Copy installed packages from deps
COPY --from=deps /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy application code
COPY . .

# Ensure alembic is runnable
RUN chmod +x /app/.venv/bin/alembic

# Run migrations then start the server
CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2"]

EXPOSE 8000

# Readiness probe
HEALTHCHECK --interval=15s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -sf http://localhost:8000/health/ready || exit 1
