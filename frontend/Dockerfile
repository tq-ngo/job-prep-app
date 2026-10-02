FROM node:20-alpine AS builder

ENV NEXT_TELEMETRY_DISABLED=1

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .

# NEXT_PUBLIC_* values are inlined into the CLIENT bundle at BUILD time, so
# supplying this only at runtime (as docker-compose previously did) had no
# effect: the browser fell back to the hardcoded "http://localhost:8000"
# default in src/lib/api.ts, which works on a localhost demo and silently
# breaks on any other host. It must be a build arg.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

RUN npm run build

# ── Production image ─────────────────────────────────────────────────────
FROM node:20-alpine AS runner

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
