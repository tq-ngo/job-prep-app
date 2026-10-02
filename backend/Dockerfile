# ── Build stage: compile wheels so the runtime image needs no toolchain ──
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


# ── Runtime stage ────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# curl is kept for the compose healthcheck. build-essential/libpq-dev are
# deliberately NOT installed here — they only existed to build wheels, and
# shipping them bloated the image and widened the attack surface.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt \
 && rm -rf /wheels

WORKDIR /app

# Run as a non-root user.
RUN groupadd --system --gid 1001 appuser \
 && useradd --system --uid 1001 --gid appuser appuser

COPY --chown=appuser:appuser . .

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
