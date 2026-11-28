# syntax=docker/dockerfile:1
#
# Single stage. Every pinned dependency ships a manylinux wheel for both
# amd64 and arm64, so --only-binary enforces reproducible builds without
# shipping compilers in the runtime image.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --only-binary=:all: -r requirements.txt

# Run as a non-root user. Application source stays owned by root:root so
# runtime processes (API and Celery workers) cannot modify code in /app.
# /var/lib/celery is pre-created for the named Beat schedule volume.
RUN groupadd --system --gid 1001 appuser \
 && useradd --system --uid 1001 --gid appuser appuser \
 && mkdir -p /var/lib/celery \
 && chown appuser:appuser /var/lib/celery

COPY . .

USER appuser

EXPOSE 8000

# Readiness probe via Python stdlib (verifies Postgres + Redis connectivity).
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/readyz', timeout=4).status == 200 else 1)"]

# Trusted proxies come from FORWARDED_ALLOW_IPS in the environment (uvicorn
# reads it natively; compose sets nginx's address).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--timeout-graceful-shutdown", "25"]
