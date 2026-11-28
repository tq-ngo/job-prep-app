# syntax=docker/dockerfile:1
# Node 22 is the active LTS.
FROM node:22-alpine AS builder

ENV NEXT_TELEMETRY_DISABLED=1

WORKDIR /app

COPY package.json package-lock.json* ./
RUN --mount=type=cache,target=/root/.npm npm ci

COPY . .

# NEXT_PUBLIC_* values are inlined into the CLIENT bundle at BUILD time.
# Empty = same-origin (relative /api/... behind nginx), the supported setup
# so SameSite=Lax auth cookies work without cross-site issues.
ARG NEXT_PUBLIC_API_URL=
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
# Destination of the dev /api rewrite in next.config.ts.
ARG INTERNAL_API_URL=http://backend:8000
ENV INTERNAL_API_URL=${INTERNAL_API_URL}
# The landing page is prerendered at build time, so metadataBase / og:image
# need the public origin at build time as well as runtime.
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

# Run as a non-root user. Application code stays owned by root:root (read-only
# to nextjs); only .next/cache is writable so ISR page caching works.
RUN addgroup --system --gid 1001 nodejs \
 && adduser --system --uid 1001 nextjs

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
RUN mkdir -p .next/cache && chown -R nextjs:nodejs .next/cache

USER nextjs

EXPOSE 3000

# Lightweight internal health route (never touches `/` ISR or backend stats).
HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=3 \
    CMD ["node", "-e", "fetch('http://127.0.0.1:3000/api/health').then(r => process.exit(r.status === 200 ? 0 : 1), () => process.exit(1))"]

CMD ["node", "server.js"]
