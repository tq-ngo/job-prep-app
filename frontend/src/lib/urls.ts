/**
 * URL helpers with no runtime dependencies, safe to import from server
 * components (unlike lib/api.ts, which builds an axios client).
 */

/**
 * API origin. Empty (the default) means same-origin: the browser calls
 * relative `/api/...` paths, which nginx (compose) or the Next rewrite (bare
 * `next dev`) forwards to FastAPI. Same-origin is what lets the auth cookies
 * the backend sets be visible to proxy.ts and work under SameSite=Lax on a
 * real domain; a separate API host only ever worked on localhost because
 * cookies ignore ports. `??` (not `||`) so an explicit "" is honoured.
 */
export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

/** Public origin of the site, for absolute URLs in metadata (server-only). */
export const SITE_URL = process.env.SITE_URL || "http://localhost";

export const googleLoginUrl = (next = "/jobs") =>
  `${API_BASE}/api/v1/auth/google/login?next=${encodeURIComponent(next)}`;
