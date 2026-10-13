# syntax=docker/dockerfile:1
#
# Single stage. Every pinned dependency ships a manylinux wheel for both
# amd64 and arm64, so the old builder stage (build-essential + libpq-dev,
# ~200 MB of toolchain layers) only ever repacked wheels. --only-binary
# makes that an enforced invariant: a dependency that would need a compiler
# now fails the build instead of silently requiring one.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --only-binary=:all: -r requirements.txt

# Run as a non-root user.
RUN groupadd --system --gid 1001 appuser \
 && useradd --system --uid 1001 --gid appuser appuser

COPY --chown=appuser:appuser . .

USER appuser

EXPOSE 8000

# Python stdlib instead of curl, so the image needs no apt packages at all.
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
