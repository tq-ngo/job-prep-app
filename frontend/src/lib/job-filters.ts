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

/** Mirrors the API's max_length on `q`. */
const MAX_QUERY_LENGTH = 200;

export interface JobFilters {
  q: string;
  category: string;
  source: string;
  remote: boolean;
  page: number;
}

export type FilterKey = "q" | "category" | "source" | "remote";
export const FILTER_KEYS: FilterKey[] = ["q", "category", "source", "remote"];

/**
 * Read filters from URL params. Unknown values fall back to "no filter"
 * instead of reaching the API, so a hand-edited or stale link still works.
 */
export function parseJobFilters(get: (key: string) => string | null | undefined): JobFilters {
  const category = get("category") ?? "";
  const source = get("source") ?? "";
  const remote = get("remote");
  const page = Number.parseInt(get("page") ?? "", 10);
  return {
    q: (get("q") ?? "").trim().slice(0, MAX_QUERY_LENGTH),
    category: (CATEGORIES as readonly string[]).includes(category) ? category : "",
    source: SOURCES.some((s) => s.value === source) ? source : "",
    remote: remote === "true" || remote === "1",
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
}

/** API query parameters for these filters, omitting the unset ones. */
export function toListParams(f: JobFilters): JobListParams {
  return {
    page: f.page,
    page_size: PAGE_SIZE,
    ...(f.q && { q: f.q }),
    ...(f.category && { category: f.category }),
    ...(f.source && { source: f.source }),
    ...(f.remote && { is_remote: true }),
  };
}

export function sameFilters(a: JobFilters, b: JobFilters): boolean {
  return FILTER_KEYS.every((k) => a[k] === b[k]) && a.page === b.page;
}

export function hasActiveFilters(f: JobFilters): boolean {
  return Boolean(f.q || f.category || f.source || f.remote);
}
