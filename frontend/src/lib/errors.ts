/**
 * Turn an API failure into a sentence for the user.
 *
 * Distinguishes the cases people can act on: they're offline or the server
 * is down (no response), they're rate limited (429), or the server rejected
 * the input with a reason (4xx `detail`). 5xx details are never shown; they
 * can carry internals.
 */

export const NETWORK_ERROR = "Can't reach the server. Check your connection and try again.";
export const RATE_LIMITED = "Too many attempts. Wait a minute and try again.";

interface ErrorLike {
  response?: { status?: number; data?: { detail?: unknown } };
  request?: unknown;
  code?: string;
}

export function errorStatus(err: unknown): number | undefined {
  return (err as ErrorLike)?.response?.status;
}

export function apiErrorMessage(
  err: unknown,
  { byStatus = {}, fallback }: { byStatus?: Record<number, string>; fallback: string },
): string {
  const e = err as ErrorLike;
  const status = e?.response?.status;
  if (status === undefined) {
    // Axios sets `request` (and ERR_NETWORK) when nothing came back.
    return e?.request || e?.code === "ERR_NETWORK" ? NETWORK_ERROR : fallback;
  }
  if (byStatus[status]) return byStatus[status];
  if (status === 429) return RATE_LIMITED;
  if (status >= 500) return fallback;

  const detail = e.response?.data?.detail;
  if (typeof detail === "string" && detail) return detail;
  if (Array.isArray(detail)) {
    // Pydantic validation errors: [{ msg: "Value error, ..." }, ...]
    const messages = detail
      .map((d: { msg?: unknown }) => (typeof d?.msg === "string" ? d.msg.replace(/^Value error,\s*/i, "") : ""))
      .filter(Boolean);
    if (messages.length) return messages.join(". ") + (messages.at(-1)!.endsWith(".") ? "" : ".");
  }
  return fallback;
}
