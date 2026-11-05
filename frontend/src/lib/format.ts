import type { JobSummary } from "@/lib/api";

// Fixed locale: server and browser must format identically, or the
// server-rendered text and the hydrated text disagree.
const LOCALE = "en-US";

const dateFormat = new Intl.DateTimeFormat(LOCALE, { month: "short", day: "numeric", year: "numeric" });
const relativeFormat = new Intl.RelativeTimeFormat(LOCALE, { numeric: "auto" });

/** "Mar 1, 2026" */
export function formatDate(iso: string): string {
  return dateFormat.format(new Date(iso));
}

const DAY = 86_400_000;
const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 365 * DAY],
  ["month", 30 * DAY],
  ["week", 7 * DAY],
  ["day", DAY],
];

/**
 * "today", "yesterday", "3 days ago", "last week"... Day granularity:
 * posting dates are often date-only, so hours would be false precision.
 */
export function formatPostedAgo(iso: string, now: number = Date.now()): string {
  const elapsed = now - new Date(iso).getTime();
  if (elapsed < DAY) return "today";
  for (const [unit, ms] of UNITS) {
    if (elapsed >= ms) return relativeFormat.format(-Math.floor(elapsed / ms), unit);
  }
  return "today";
}

/** "$60 – $75/hr", "$120,000/yr", or null when the posting lists no pay. */
export function formatPay(job: Pick<JobSummary, "salary_min" | "salary_max" | "salary_period">): string | null {
  const { salary_min: lo, salary_max: hi, salary_period: period } = job;
  if (!lo && !hi) return null;
  const fmt = (n: number) => `$${n.toLocaleString(LOCALE)}`;
  const range = lo && hi && lo !== hi ? `${fmt(lo)} – ${fmt(hi)}` : fmt((lo || hi)!);
  return period === "hour" ? `${range}/hr` : period === "year" ? `${range}/yr` : range;
}

/** Location line for a job, falling back to "Remote" or a placeholder. */
export function formatLocation(job: Pick<JobSummary, "location" | "is_remote">, fallback = "Location unspecified"): string {
  return job.location || (job.is_remote ? "Remote" : fallback);
}
