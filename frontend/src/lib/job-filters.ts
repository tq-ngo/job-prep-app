/**
 * The job board's filters as they live in the URL, shared by the server page
 * (which seeds the first render) and the client feed, so both read the same
 * URL the same way.
 */

export const PAGE_SIZE = 30;

export const CATEGORIES = ["FAANG+", "Quant", "Others"] as const;
export const SOURCES = [
  { value: "github", label: "GitHub" },
  { value: "linkedin", label: "LinkedIn" },
] as const;

export const SPONSORSHIPS = [
  { value: "sponsorship_available", label: "Sponsorship Available" },
  { value: "requires_citizenship", label: "US Citizen Required" },
] as const;

export const WORK_TYPES = [
  { value: "remote", label: "Remote" },
  { value: "hybrid", label: "Hybrid" },
  { value: "onsite", label: "On-site" },
] as const;

export const SORT_OPTIONS = [
  { value: "date", label: "Latest Date" },
  { value: "relevance", label: "Most Relevant" },
] as const;

/** Mirrors the API's max_length on `q`. */
const MAX_QUERY_LENGTH = 200;

export interface JobFilters {
  q: string;
  category: string;
  source: string;
  work_type: string;
  sponsorship: string;
  skill: string;
  sort_by: string;
  remote: boolean;
  page: number;
}

export type FilterKey = "q" | "category" | "source" | "work_type" | "sponsorship" | "skill" | "sort_by" | "remote";
export const FILTER_KEYS: FilterKey[] = [
  "q",
  "category",
  "source",
  "work_type",
  "sponsorship",
  "skill",
  "sort_by",
  "remote",
];

/**
 * Read filters from URL params. Unknown values fall back to "no filter"
 * instead of reaching the API, so a hand-edited or stale link still works.
 */
export function parseJobFilters(get: (key: string) => string | null | undefined): JobFilters {
  const category = get("category") ?? "";
  const source = get("source") ?? "";
  const work_type = get("work_type") ?? "";
  const rawSponsorship = (get("sponsorship") ?? "").toLowerCase().trim();
  const sponsorship =
    rawSponsorship === "cpt_opt" || rawSponsorship === "h1b" || rawSponsorship === "f1_eligible"
      ? "sponsorship_available"
      : rawSponsorship === "citizenship"
        ? "requires_citizenship"
        : rawSponsorship;
  const skill = (get("skill") ?? "").trim().slice(0, 50);
  const sort_by = get("sort_by") === "relevance" ? "relevance" : "date";
  const remoteParam = get("remote");
  const remote = remoteParam === "true" || remoteParam === "1" || work_type === "remote";
  const effectiveWorkType = work_type || (remote ? "remote" : "");
  const page = Number.parseInt(get("page") ?? "", 10);

  return {
    q: (get("q") ?? "").trim().slice(0, MAX_QUERY_LENGTH),
    category: (CATEGORIES as readonly string[]).includes(category) ? category : "",
    source: SOURCES.some((s) => s.value === source) ? source : "",
    work_type: WORK_TYPES.some((w) => w.value === effectiveWorkType) ? effectiveWorkType : "",
    sponsorship: SPONSORSHIPS.some((s) => s.value === sponsorship) ? sponsorship : "",
    skill,
    sort_by,
    remote: effectiveWorkType === "remote",
    page: Number.isFinite(page) && page > 1 ? page : 1,
  };
}

export interface JobListParams {
  page: number;
  page_size: number;
  q?: string;
  category?: string;
  source?: string;
  is_remote?: boolean;
  work_type?: string;
  sponsorship?: string;
  skill?: string;
  sort_by?: string;
}

/** API query parameters for these filters, omitting the unset ones. */
export function toListParams(f: JobFilters): JobListParams {
  return {
    page: f.page,
    page_size: PAGE_SIZE,
    ...(f.q && { q: f.q }),
    ...(f.category && { category: f.category }),
    ...(f.source && { source: f.source }),
    ...(f.work_type && { work_type: f.work_type }),
    ...(f.sponsorship && { sponsorship: f.sponsorship }),
    ...(f.skill && { skill: f.skill }),
    ...(f.sort_by && f.sort_by !== "date" && { sort_by: f.sort_by }),
    ...(f.remote && { is_remote: true }),
  };
}

export function sameFilters(a: JobFilters, b: JobFilters): boolean {
  return FILTER_KEYS.every((k) => a[k] === b[k]) && a.page === b.page;
}

export function hasActiveFilters(f: JobFilters): boolean {
  return Boolean(
    f.q ||
    f.category ||
    f.source ||
    f.work_type ||
    f.sponsorship ||
    f.skill ||
    (f.sort_by && f.sort_by !== "date") ||
    f.remote,
  );
}
