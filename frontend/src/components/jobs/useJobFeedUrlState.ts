"use client";

import { useCallback, useMemo } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { FILTER_KEYS, parseJobFilters, type FilterKey } from "@/lib/job-filters";

type Update = (params: URLSearchParams) => void;

/**
 * The job board's state lives in the URL (filters, page, open job), so
 * reloads, shared links and Back/Forward all restore it.
 *
 * Writes go through window.history, not router.push: Next syncs
 * useSearchParams with pushState/replaceState without a server round trip.
 */
export function useJobFeedUrlState() {
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const filters = useMemo(() => parseJobFilters((k) => searchParams.get(k)), [searchParams]);
  const activeJobId = searchParams.get("jobId");

  const hrefWith = useCallback(
    (update: Update) => {
      const params = new URLSearchParams(searchParams.toString());
      update(params);
      const qs = params.toString();
      return qs ? `${pathname}?${qs}` : pathname;
    },
    [pathname, searchParams],
  );

  // Read live window.location.search on imperative writes so back-to-back calls
  // within the same render tick never clobber each other with a stale closure.
  const go = useCallback(
    (update: Update, mode: "push" | "replace") => {
      const currentSearch =
        typeof window !== "undefined" ? window.location.search : searchParams.toString();
      const params = new URLSearchParams(currentSearch);
      update(params);
      const qs = params.toString();
      const url = qs ? `${pathname}?${qs}` : pathname;
      if (mode === "push") window.history.pushState(null, "", url);
      else window.history.replaceState(null, "", url);
    },
    [pathname, searchParams],
  );

  /** A new filter starts over: page 1, and the first result instead of the old job. */
  const setFilter = useCallback(
    (key: FilterKey, value: string) =>
      go((p) => {
        if (value) p.set(key, value);
        else p.delete(key);
        // Legacy ?remote=true alias must be cleared whenever work_type changes or resets.
        if (key === "work_type") p.delete("remote");
        p.delete("page");
        p.delete("jobId");
      }, "replace"),
    [go],
  );

  const clearFilters = useCallback(
    () =>
      go((p) => {
        FILTER_KEYS.forEach((k) => p.delete(k));
        p.delete("remote");
        p.delete("page");
        p.delete("jobId");
      }, "replace"),
    [go],
  );

  const setPage = useCallback(
    (page: number) =>
      go((p) => {
        if (page > 1) p.set("page", String(page));
        else p.delete("page");
        p.delete("jobId");
      }, "push"),
    [go],
  );

  const jobHref = useCallback((id: string) => hrefWith((p) => p.set("jobId", id)), [hrefWith]);
  const openJob = useCallback((id: string) => go((p) => p.set("jobId", id), "push"), [go]);
  const closeJob = useCallback(
    (mode: "push" | "replace" = "push") => go((p) => p.delete("jobId"), mode),
    [go],
  );

  return { filters, activeJobId, setFilter, clearFilters, setPage, jobHref, openJob, closeJob };
}
