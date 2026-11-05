/**
 * Base URL for server-side fetches (server components, ISR). The browser
 * talks to the same-origin /api through nginx; the server can't, so it uses
 * the backend's address on the internal network.
 */
export const INTERNAL_API_URL = process.env.INTERNAL_API_URL || "http://localhost:8000";
