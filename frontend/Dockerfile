# syntax=docker/dockerfile:1
# Node 20 reached end-of-life in April 2026; 22 is the active LTS.
FROM node:22-alpine AS builder

ENV NEXT_TELEMETRY_DISABLED=1

WORKDIR /app

COPY package.json package-lock.json* ./
RUN --mount=type=cache,target=/root/.npm npm ci

COPY . .

# NEXT_PUBLIC_* values are inlined into the CLIENT bundle at BUILD time, so
# supplying this only at runtime (as docker-compose previously did) had no
# effect: the browser fell back to the hardcoded "http://localhost:8000"
# default in src/lib/api.ts, which works on a localhost demo and silently
# breaks on any other host. It must be a build arg.
# Empty = same-origin (relative /api/... behind nginx), the supported setup.
ARG NEXT_PUBLIC_API_URL=
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
# Destination of the /api rewrite in next.config.ts (resolved at build time).
ARG INTERNAL_API_URL=http://backend:8000
ENV INTERNAL_API_URL=${INTERNAL_API_URL}
# The landing page is prerendered at build time, so its absolute metadata
# URLs (metadataBase, og:image) need the public origin now, not just at runtime.
ARG SITE_URL=http://localhost
ENV SITE_URL=${SITE_URL}

RUN npm run build

# ── Production image ─────────────────────────────────────────────────────
FROM node:22-alpine AS runner

ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

WORKDIR /app

# Run as a non-root user (the canonical Next standalone setup).
RUN addgroup --system --gid 1001 nodejs \
 && adduser --system --uid 1001 nextjs

# Copy the standalone output (includes server + minimal deps)
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
# Copy static assets and public directory
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

USER nextjs

EXPOSE 3000

CMD ["node", "server.js"]
