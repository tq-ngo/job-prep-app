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
import Badge from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import EmptyState from "@/components/ui/EmptyState";
import { Input, Select } from "@/components/ui/Input";
import Skeleton from "@/components/ui/Skeleton";

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
        <div className="max-w-app mx-auto px-4 sm:px-6 lg:px-8 py-2 flex flex-wrap items-center gap-2">
          <h1 className="text-base font-serif font-medium text-slate-ink tracking-tight mr-1">Job Board</h1>
          <span className="font-mono text-2xs text-foreground-subtle uppercase tracking-wider mr-2 whitespace-nowrap">
            {currentData ? `${currentData.total}${currentData.capped ? "+" : ""} roles` : "Loading…"}
          </span>
          <span
            className="inline-flex items-center gap-1.5 font-mono text-2xs uppercase tracking-wider text-foreground-subtle mr-auto"
            title={sseConnected ? "Live updates connected" : "Live updates disconnected"}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${sseConnected ? "bg-spruce-green animate-pulse" : "bg-slate-soft"}`}
            />
            <span className="hidden sm:inline">{sseConnected ? "Live" : "Offline"}</span>
          </span>

          {/* Search Bar */}
          <Input
            size="sm"
            type="search"
            leadingIcon={<Search size={14} />}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search role or company…"
            aria-label="Search role or company"
            className="w-full sm:w-64 order-last sm:order-none"
          />

          <Select
            size="sm"
            aria-label="Category"
            value={category}
            onChange={(e) => { setCategory(e.target.value); resetToFirstPage(); }}
          >
            <option value="">All Categories</option>
            <option value="FAANG+">FAANG+</option>
            <option value="Quant">Quant</option>
            <option value="Others">Others</option>
          </Select>

          <Select
            size="sm"
            aria-label="Source"
            value={source}
            onChange={(e) => { setSource(e.target.value); resetToFirstPage(); }}
          >
            <option value="">All Sources</option>
            <option value="github">GitHub</option>
            <option value="linkedin">LinkedIn</option>
          </Select>

          <Button
            variant="secondary"
            size="sm"
            aria-pressed={isRemote}
            onClick={() => { setIsRemote(!isRemote); resetToFirstPage(); }}
          >
            Remote
          </Button>

          <Button
            size="sm"
            onClick={handleRefreshScrapers}
            loading={isScraping}
            icon={<RefreshCw size={12} aria-hidden="true" />}
          >
            {isScraping ? "Syncing…" : "Refresh"}
          </Button>
        </div>
      </div>

      {/* Main Content Area: High-Density Table */}
      <div className="max-w-app mx-auto px-4 sm:px-6 lg:px-8 py-3">

        {pendingNew > 0 && (
          <div className="flex justify-center mb-3">
            <button
              type="button"
              onClick={showPendingJobs}
              className="font-mono text-2xs uppercase tracking-wider px-3 py-1.5 rounded-full bg-spruce-green text-warm-ivory shadow-card hover:bg-spruce-green-hover transition-colors"
            >
              ↑ {pendingNew} new {pendingNew === 1 ? "job" : "jobs"}
            </button>
          </div>
        )}

        {/* Empty state */}
        {!isLoading && currentJobs.length === 0 && (
          <EmptyState
            icon={<Briefcase size={22} />}
            title="No positions found"
            description={
              debouncedSearch
                ? `No job matches for "${debouncedSearch}". Try a different keyword or clear your filters.`
                : "The board is waiting for the daily crawler or manual refresh."
            }
            action={
              debouncedSearch && (
                <Button variant="secondary" size="sm" onClick={() => setSearchQuery("")}>
                  Clear Search
                </Button>
              )
            }
          />
        )}

        {/* 6-Column Data Feed Table */}
        {/* The skeleton rows are aria-hidden; this is what screen readers hear. */}
        {isLoading && (
          <p role="status" className="sr-only">
            Loading jobs
          </p>
        )}

        {(isLoading || currentJobs.length > 0) && (
          <div className="border border-slate-soft rounded-card overflow-hidden bg-background shadow-card">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-soft bg-neutral-soft/50">
                    <th className="px-4 py-2 font-mono text-2xs font-semibold uppercase tracking-wider text-foreground-subtle">Role</th>
                    <th className="px-4 py-2 font-mono text-2xs font-semibold uppercase tracking-wider text-foreground-subtle">Company</th>
                    <th className="px-4 py-2 font-mono text-2xs font-semibold uppercase tracking-wider text-foreground-subtle">Location</th>
                    <th className="px-4 py-2 font-mono text-2xs font-semibold uppercase tracking-wider text-foreground-subtle">Source</th>
                    <th className="px-4 py-2 font-mono text-2xs font-semibold uppercase tracking-wider text-foreground-subtle text-right">Apply</th>
                    <th className="px-4 py-2 font-mono text-2xs font-semibold uppercase tracking-wider text-foreground-subtle text-right">Posted</th>
                  </tr>
                </thead>
                <tbody>
                  {isLoading ? (
                    Array.from({ length: 10 }).map((_, i) => (
                      <tr key={i} className="border-b border-slate-soft/50">
                        <td colSpan={6} className="px-4 py-2.5">
                          <div className="flex gap-6">
                            <Skeleton className="h-3.5 w-48" />
                            <Skeleton className="h-3.5 w-24" />
                            <Skeleton className="h-3.5 w-32" />
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
                            <Badge variant="source">{job.source}</Badge>
                          </td>
                          <td className="px-4 py-2 text-right">
                            <a
                              href={job.apply_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              onClick={(e) => e.stopPropagation()}
                              className="inline-flex items-center gap-1 px-2.5 py-0.5 text-2xs font-sans font-medium text-spruce-green bg-spruce-green/5 border border-spruce-green/30 hover:border-spruce-green hover:bg-spruce-green/10 rounded transition-all"
                            >
                              Apply <ExternalLink size={11} />
                            </a>
                          </td>
                          <td className="px-4 py-2 text-right font-mono text-2xs text-foreground-subtle whitespace-nowrap">
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
            <span className="font-mono text-2xs text-foreground-subtle uppercase tracking-wider">
              Page {page} of {currentData.pages} ({currentData.total}{currentData.capped ? "+" : ""} total)
            </span>
            <div className="flex gap-2">
              <Button variant="secondary" size="sm" onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1}>
                Prev
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setPage(Math.min(currentData.pages, page + 1))}
                disabled={page === currentData.pages}
              >
                Next
              </Button>
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
