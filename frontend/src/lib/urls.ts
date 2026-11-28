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

const CONTROL_CHAR_RE = /[\x00-\x1f\x7f]/;
const ENCODED_CONTROL_CHAR_RE = /%(?:0[0-9a-f]|1[0-9a-f]|7f)/i;

/**
 * A post-login destination from the query string, or /jobs. Only same-origin
 * relative paths: blocks absolute URLs, protocol-relative URLs (`//evil.com`),
 * backslashes (`/\evil.com`), and raw or percent-encoded ASCII control
 * characters (`/\t/evil.com`, `/%09/evil.com`) that WHATWG URL parsers strip.
 */
export function safeNextPath(next: string | undefined | null, fallback = "/jobs"): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.includes("\\")) {
    return fallback;
  }
  if (CONTROL_CHAR_RE.test(next) || ENCODED_CONTROL_CHAR_RE.test(next)) {
    return fallback;
  }
  try {
    const parsed = new URL(next, "http://localhost");
    if (parsed.origin !== "http://localhost") {
      return fallback;
    }
    return next;
  } catch {
    return fallback;
  }
}
