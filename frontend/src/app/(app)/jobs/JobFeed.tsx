"use client";

import { useState, useCallback, useEffect } from "react";
import dynamic from "next/dynamic";
import { useJob, useJobs, usePrefetchJob, useTriggerScrape } from "@/hooks/useJobs";
import { useQueryClient } from "@tanstack/react-query";
import { JobEvent, JobListResponse, JobSummary } from "@/lib/api";
import { Search, ExternalLink, RefreshCw, Briefcase } from "lucide-react";
import { useScrapePolling } from "@/hooks/useScrapePolling";
import { useJobAlerts } from "@/hooks/useJobAlerts";
import { useSearchParams, useRouter, usePathname } from "next/navigation";

// The drawer pulls in react-markdown + remark-gfm; load it only when a job is
// first opened instead of on the board's critical path.
const JobDetailsSidebar = dynamic(() => import("@/components/JobDetailsSidebar"), {
  ssr: false,
});

const PAGE_SIZE = 30;

interface JobFeedProps {
  initialData?: JobListResponse;
  initialDataUpdatedAt?: number;
}

const selectClass =
  "appearance-none bg-background border border-slate-soft hover:border-slate-soft/80 text-slate-ink text-xs font-sans rounded px-2.5 h-8 focus:outline-none focus:ring-1 focus:ring-spruce-green transition-all cursor-pointer";

export default function JobFeed({ initialData, initialDataUpdatedAt }: JobFeedProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  // URL is the source of truth for the page and the open job, so Back/Forward
  // and shared links restore both.
  const page = Math.max(1, Number(searchParams.get("page")) || 1);
  const activeJobId = searchParams.get("jobId");

  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");

  // Server-side filters
  const [category, setCategory] = useState("");
  const [source, setSource] = useState("");
  const [isRemote, setIsRemote] = useState(false);

  // Scraping state for the pull mechanism
  const [taskId, setTaskId] = useState<string | null>(null);

  const queryClient = useQueryClient();
  const prefetchJob = usePrefetchJob();

  const setParams = useCallback(
    (update: (params: URLSearchParams) => void, mode: "push" | "replace" = "push") => {
      const params = new URLSearchParams(searchParams.toString());
      update(params);
      const qs = params.toString();
      const url = qs ? `${pathname}?${qs}` : pathname;
      if (mode === "push") router.push(url, { scroll: false });
      else router.replace(url, { scroll: false });
    },
    [pathname, router, searchParams],
  );

  const setPage = useCallback(
    (next: number, mode: "push" | "replace" = "push") =>
      setParams((p) => (next > 1 ? p.set("page", String(next)) : p.delete("page")), mode),
    [setParams],
  );

  // Debounce search input to query server across all database rows
  useEffect(() => {
    const next = searchQuery.trim();
    if (next === debouncedSearch) return;
    const timer = setTimeout(() => {
      setDebouncedSearch(next);
      setPage(1, "replace");
    }, 350);
    return () => clearTimeout(timer);
  }, [searchQuery, debouncedSearch, setPage]);

  // New postings are counted, not auto-inserted: invalidating the list on
  // every event refetched once per job (125 refetches per crawl, per tab) and
  // reshuffled rows under the user's cursor. `enriched` events only add
  // skills, which the list doesn't show, so they don't count.
  const [pendingNew, setPendingNew] = useState(0);
  const { connected: sseConnected } = useJobAlerts({
    onEvent: useCallback((event: JobEvent) => {
      if (event.kind === "created") setPendingNew((n) => n + 1);
    }, []),
  });

  const showPendingJobs = () => {
    setPendingNew(0);
    setPage(1);
    queryClient.invalidateQueries({ queryKey: ["jobs"] });
  };

  const isDefaultState = page === 1 && !isRemote && !source && !category && !debouncedSearch;

  // Data fetching: combines server pagination + debounced search + filters
  const { data: currentData, isLoading, refetch } = useJobs(
    {
      page,
      page_size: PAGE_SIZE,
      category: category || undefined,
      is_remote: isRemote || undefined,
      source: source || undefined,
      q: debouncedSearch || undefined,
    },
    isDefaultState ? { initialData, initialDataUpdatedAt } : {},
  );
  const currentJobs = currentData?.items ?? [];

  const triggerScrape = useTriggerScrape();

  const onScrapeComplete = useCallback(() => {
    setTaskId(null);
    refetch();
  }, [refetch]);

  useScrapePolling(taskId, onScrapeComplete);

  const handleRefreshScrapers = () => {
    refetch();
    triggerScrape.mutate(source || "all", {
      onSuccess: (data) => {
        if (data.task_id) setTaskId(data.task_id);
        else refetch();
      },
    });
  };

  // Drawer: the row (if on this page) is placeholder data while the full job
  // — including its description — loads by id. Deep links to a job on
  // another page fetch it directly. Deriving this from the URL replaced an
  // effect that mirrored ?jobId= into state.
  const rowForActive = currentJobs.find((j) => j.id === activeJobId);
  const { data: activeJob, isPlaceholderData } = useJob(activeJobId, rowForActive);

  // Mount the drawer on first open, then keep it mounted so closing can
  // animate out (and the lazily loaded chunk isn't re-requested).
  const [drawerMounted, setDrawerMounted] = useState(!!activeJobId);
  if (activeJobId && !drawerMounted) setDrawerMounted(true);

  const handleSelectJob = (job: JobSummary) => setParams((p) => p.set("jobId", job.id));
  const handleCloseDrawer = useCallback(() => setParams((p) => p.delete("jobId")), [setParams]);

  const resetToFirstPage = () => setPage(1, "replace");
  const isScraping = triggerScrape.isPending || !!taskId;

  return (
    <div className="min-h-screen bg-background text-foreground font-sans">

      {/* One compact sticky toolbar under the h-12 navbar. This used to be
          ~230px of title, subtitle and a separate filter row. */}
      <div className="sticky top-12 z-30 bg-background/95 backdrop-blur-sm border-b border-slate-soft">
        <div className="max-w-[1500px] mx-auto px-4 sm:px-6 lg:px-8 py-2 flex flex-wrap items-center gap-2">
          <h1 className="text-base font-serif font-medium text-slate-ink tracking-tight mr-1">Job Board</h1>
          <span className="font-mono text-[11px] text-foreground-subtle uppercase tracking-wider mr-2 whitespace-nowrap">
            {currentData ? `${currentData.total}${currentData.capped ? "+" : ""} roles` : "Loading…"}
          </span>
          <span
            className="inline-flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-wider text-foreground-subtle mr-auto"
            title={sseConnected ? "Live updates connected" : "Live updates disconnected"}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${sseConnected ? "bg-spruce-green animate-pulse" : "bg-slate-soft"}`}
            />
            <span className="hidden sm:inline">{sseConnected ? "Live" : "Offline"}</span>
          </span>

          {/* Search Bar */}
          <div className="relative w-full sm:w-64 order-last sm:order-none">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-foreground-subtle" />
            <input
              type="search"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search role or company…"
              aria-label="Search role or company"
              className="w-full pl-8 pr-2 h-8 bg-background border border-slate-soft rounded focus:outline-none focus:ring-1 focus:ring-spruce-green text-xs text-slate-ink placeholder:text-foreground-subtle font-sans"
            />
          </div>

          <select
            aria-label="Category"
            value={category}
            onChange={(e) => { setCategory(e.target.value); resetToFirstPage(); }}
            className={selectClass}
          >
            <option value="">All Categories</option>
            <option value="FAANG+">FAANG+</option>
            <option value="Quant">Quant</option>
            <option value="Others">Others</option>
          </select>

          <select
            aria-label="Source"
            value={source}
            onChange={(e) => { setSource(e.target.value); resetToFirstPage(); }}
            className={selectClass}
          >
            <option value="">All Sources</option>
            <option value="github">GitHub</option>
            <option value="linkedin">LinkedIn</option>
          </select>

          <button
            type="button"
            aria-pressed={isRemote}
            onClick={() => { setIsRemote(!isRemote); resetToFirstPage(); }}
            className={`text-xs font-sans font-medium rounded px-2.5 h-8 border transition-all ${
              isRemote
                ? "bg-amber-clay/10 border-amber-clay/40 text-amber-clay"
                : "bg-background border-slate-soft hover:border-slate-soft/80 text-slate-ink"
            }`}
          >
            Remote
          </button>

          <button
            onClick={handleRefreshScrapers}
            disabled={isScraping}
            className="flex items-center gap-1.5 bg-spruce-green hover:bg-spruce-green-hover disabled:bg-slate-soft disabled:text-foreground-subtle disabled:cursor-not-allowed text-warm-ivory px-3 h-8 rounded font-sans font-medium transition-colors text-xs"
          >
            <RefreshCw size={12} className={isScraping ? "animate-spin" : ""} />
            {isScraping ? "Syncing…" : "Refresh"}
          </button>
        </div>
      </div>

      {/* Main Content Area: High-Density Table */}
      <div className="max-w-[1500px] mx-auto px-4 sm:px-6 lg:px-8 py-3">

        {pendingNew > 0 && (
          <div className="flex justify-center mb-3">
            <button
              type="button"
              onClick={showPendingJobs}
              className="font-mono text-[11px] uppercase tracking-wider px-3 py-1.5 rounded-full bg-spruce-green text-warm-ivory shadow-sm hover:bg-spruce-green-hover transition-colors"
            >
              ↑ {pendingNew} new {pendingNew === 1 ? "job" : "jobs"}
            </button>
          </div>
        )}

        {/* Empty state */}
        {!isLoading && currentJobs.length === 0 && (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <div className="w-14 h-14 rounded-lg bg-neutral-soft border border-slate-soft flex items-center justify-center mb-4">
              <Briefcase size={22} className="text-foreground-subtle" />
            </div>
            <h2 className="text-lg font-serif text-slate-ink mb-1.5">No positions found</h2>
            <p className="text-foreground-muted mb-5 max-w-sm font-sans text-xs leading-relaxed">
              {debouncedSearch
                ? `No job matches for "${debouncedSearch}". Try a different keyword or clear your filters.`
                : "The board is waiting for the daily crawler or manual refresh."}
            </p>
            {debouncedSearch && (
              <button
                onClick={() => setSearchQuery("")}
                className="px-3.5 py-1.5 bg-neutral-soft border border-slate-soft rounded text-xs text-slate-ink hover:border-spruce-green"
              >
                Clear Search
              </button>
            )}
          </div>
        )}

        {/* 6-Column Data Feed Table */}
        {(isLoading || currentJobs.length > 0) && (
          <div className="border border-slate-soft rounded-lg overflow-hidden bg-background shadow-xs">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-soft bg-neutral-soft/50">
                    <th className="px-4 py-2 font-mono text-[11px] font-semibold uppercase tracking-wider text-foreground-subtle">Role</th>
                    <th className="px-4 py-2 font-mono text-[11px] font-semibold uppercase tracking-wider text-foreground-subtle">Company</th>
                    <th className="px-4 py-2 font-mono text-[11px] font-semibold uppercase tracking-wider text-foreground-subtle">Location</th>
                    <th className="px-4 py-2 font-mono text-[11px] font-semibold uppercase tracking-wider text-foreground-subtle">Source</th>
                    <th className="px-4 py-2 font-mono text-[11px] font-semibold uppercase tracking-wider text-foreground-subtle text-right">Apply</th>
                    <th className="px-4 py-2 font-mono text-[11px] font-semibold uppercase tracking-wider text-foreground-subtle text-right">Posted</th>
                  </tr>
                </thead>
                <tbody>
                  {isLoading ? (
                    Array.from({ length: 10 }).map((_, i) => (
                      <tr key={i} className="border-b border-slate-soft/50">
                        <td colSpan={6} className="px-4 py-2.5">
                          <div className="animate-pulse flex gap-6">
                            <div className="h-3.5 w-48 bg-slate-soft rounded" />
                            <div className="h-3.5 w-24 bg-slate-soft/60 rounded" />
                            <div className="h-3.5 w-32 bg-slate-soft/60 rounded" />
                          </div>
                        </td>
                      </tr>
                    ))
                  ) : (
                    currentJobs.map((job) => {
                      const isSelected = activeJobId === job.id;
                      return (
                        <tr
                          key={job.id}
                          onClick={() => handleSelectJob(job)}
                          onMouseEnter={() => prefetchJob(job.id)}
                          onFocus={() => prefetchJob(job.id)}
                          className={`border-b border-slate-soft/50 last:border-b-0 hover:bg-slate-soft/20 cursor-pointer transition-colors group ${
                            isSelected ? "bg-spruce-green/5 border-l-2 border-l-spruce-green" : ""
                          }`}
                          role="button"
                          tabIndex={0}
                          aria-label={`${job.title} at ${job.company}`}
                          onKeyDown={(e) => {
                            if (e.key === "Enter" || e.key === " ") {
                              e.preventDefault();
                              handleSelectJob(job);
                            }
                          }}
                        >
                          <td className="px-4 py-2 font-sans font-medium text-slate-ink group-hover:text-spruce-green transition-colors truncate max-w-[280px]">
                            {job.title}
                          </td>
                          <td className="px-4 py-2 font-sans text-foreground-muted truncate max-w-[160px]">
                            {job.company}
                          </td>
                          <td className="px-4 py-2 font-sans text-foreground-subtle truncate max-w-[160px]">
                            {job.location || (job.is_remote ? "Remote" : "—")}
                          </td>
                          <td className="px-4 py-2">
                            <span className="font-mono text-[11px] text-amber-clay uppercase tracking-wider px-1.5 py-0.5 rounded bg-amber-clay/10">
                              {job.source}
                            </span>
                          </td>
                          <td className="px-4 py-2 text-right">
                            <a
                              href={job.apply_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              onClick={(e) => e.stopPropagation()}
                              className="inline-flex items-center gap-1 px-2.5 py-0.5 text-[11px] font-sans font-medium text-spruce-green bg-spruce-green/5 border border-spruce-green/30 hover:border-spruce-green hover:bg-spruce-green/10 rounded transition-all"
                            >
                              Apply <ExternalLink size={11} />
                            </a>
                          </td>
                          <td className="px-4 py-2 text-right font-mono text-[11px] text-foreground-subtle whitespace-nowrap">
                            {job.posted_at
                              ? new Date(job.posted_at).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })
                              : "—"}
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Pagination Bar */}
        {currentData && currentData.pages > 1 && (
          <div className="flex justify-between items-center mt-4">
            <span className="font-mono text-[11px] text-foreground-subtle uppercase tracking-wider">
              Page {page} of {currentData.pages} ({currentData.total}{currentData.capped ? "+" : ""} total)
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => setPage(Math.max(1, page - 1))}
                disabled={page === 1}
                className="px-3 py-1.5 bg-background border border-slate-soft rounded disabled:text-foreground-subtle disabled:cursor-not-allowed text-xs font-medium hover:border-slate-soft/80 transition-colors text-slate-ink"
              >
                Prev
              </button>
              <button
                onClick={() => setPage(Math.min(currentData.pages, page + 1))}
                disabled={page === currentData.pages}
                className="px-3 py-1.5 bg-background border border-slate-soft rounded disabled:text-foreground-subtle disabled:cursor-not-allowed text-xs font-medium hover:border-slate-soft/80 transition-colors text-slate-ink"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Slide-over Sheet / Drawer */}
      {drawerMounted && (
        <JobDetailsSidebar
          open={!!activeJobId}
          job={activeJob ?? null}
          isLoadingDescription={isPlaceholderData || !activeJob}
          onClose={handleCloseDrawer}
        />
      )}
    </div>
  );
}
