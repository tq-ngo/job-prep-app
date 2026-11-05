"use client";

import { useCallback, useEffect, useRef, useState, type MouseEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Briefcase } from "lucide-react";
import { JobEvent, JobListResponse, JobSummary } from "@/lib/api";
import { hasActiveFilters, sameFilters, toListParams, type JobFilters } from "@/lib/job-filters";
import { useJob, useJobs, useTriggerScrape } from "@/hooks/useJobs";
import { useJobAlerts } from "@/hooks/useJobAlerts";
import { DESKTOP_QUERY, useMediaQuery } from "@/hooks/useMediaQuery";
import { useScrapePolling } from "@/hooks/useScrapePolling";
import Alert from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { cn } from "@/components/ui/cn";
import EmptyState from "@/components/ui/EmptyState";
import JobDetailPane from "@/components/jobs/JobDetailPane";
import JobFeedToolbar from "@/components/jobs/JobFeedToolbar";
import JobList, { JobListSkeleton } from "@/components/jobs/JobList";
import JobListPagination from "@/components/jobs/JobListPagination";
import { useJobFeedUrlState } from "@/components/jobs/useJobFeedUrlState";

interface JobFeedProps {
  initialData?: JobListResponse;
  initialDataUpdatedAt?: number;
  /** The filters the server fetched initialData for (from the same URL). */
  initialFilters?: JobFilters;
}

/**
 * List and detail side by side (lg+), or one at a time below lg: the list,
 * or the selected job with a way back. Which one shows is pure CSS keyed on
 * ?jobId=, so the server HTML is already right for every screen size.
 *
 * On lg+ the two panes scroll independently and the page doesn't; below lg
 * the page scrolls normally (so mobile browsers can collapse their chrome).
 */
export default function JobFeed({ initialData, initialDataUpdatedAt, initialFilters }: JobFeedProps) {
  const { filters, activeJobId, setFilter, clearFilters, setPage, jobHref, openJob, closeJob } = useJobFeedUrlState();
  const isDesktop = useMediaQuery(DESKTOP_QUERY);
  const queryClient = useQueryClient();

  // The server seeded exactly one filter set; only that query may use it.
  const seeded = initialData && initialFilters && sameFilters(initialFilters, filters);
  const jobsQuery = useJobs(toListParams(filters), seeded ? { initialData, initialDataUpdatedAt } : {});
  const { data, isLoading, isError, isPlaceholderData, refetch } = jobsQuery;
  const jobs = data?.items ?? [];

  // ── Live updates ───────────────────────────────────────────────────────
  // New postings are counted, not auto-inserted: inserting reshuffled rows
  // under the user's cursor. `enriched` events only add skills to existing
  // rows, so they don't count.
  const [pendingNew, setPendingNew] = useState(0);
  const { connected: sseConnected } = useJobAlerts({
    onEvent: useCallback((event: JobEvent) => {
      if (event.kind === "created") setPendingNew((n) => n + 1);
    }, []),
  });

  const listPaneRef = useRef<HTMLElement>(null);
  const scrollListToTop = () => {
    listPaneRef.current?.scrollTo?.({ top: 0 });
    if (!isDesktop) window.scrollTo({ top: 0 });
  };

  const showPendingJobs = () => {
    setPendingNew(0);
    if (filters.page !== 1) setPage(1);
    scrollListToTop();
    queryClient.invalidateQueries({ queryKey: ["jobs"] });
  };

  const handlePage = (page: number) => {
    setPage(page);
    scrollListToTop();
  };

  // ── Manual scrape ──────────────────────────────────────────────────────
  const triggerScrape = useTriggerScrape();
  const [taskId, setTaskId] = useState<string | null>(null);
  const onScrapeComplete = useCallback(() => {
    setTaskId(null);
    queryClient.invalidateQueries({ queryKey: ["jobs"] });
  }, [queryClient]);
  useScrapePolling(taskId, onScrapeComplete);

  const handleRefresh = () => {
    triggerScrape.mutate(filters.source || "all", {
      onSuccess: (res) => {
        if (res.task_id) setTaskId(res.task_id);
        else onScrapeComplete();
      },
    });
  };
  const isScraping = triggerScrape.isPending || !!taskId;

  // ── Selection ──────────────────────────────────────────────────────────
  // With nothing selected, desktop shows the first result, like LinkedIn,
  // without writing it to the URL. Below lg that pane is hidden, so its
  // full job isn't fetched there.
  const defaultJobId = !activeJobId && isDesktop ? (jobs[0]?.id ?? null) : null;
  const shownId = activeJobId ?? jobs[0]?.id ?? null;
  const row = jobs.find((j) => j.id === shownId);
  const detail = useJob(activeJobId ?? defaultJobId, row);
  const shownJob = detail.data ?? row ?? null;

  const focusTitleRequestRef = useRef(false);
  const listScrollY = useRef(0);
  // Whether the open job was pushed from the list, so "Back" can pop it.
  const openedFromList = useRef(false);

  const handleSelect = (job: JobSummary, e: MouseEvent<HTMLAnchorElement>) => {
    // detail 0 = activated by keyboard. Mobile always moves focus, since the
    // list it came from disappears.
    focusTitleRequestRef.current = e.detail === 0 || !isDesktop;
    listScrollY.current = window.scrollY;
    openedFromList.current = true;
    openJob(job.id);
  };

  const handleBack = () => {
    if (openedFromList.current) window.history.back();
    else closeJob(); // deep link: there's no list entry behind us to go back to
  };

  // Below lg, the detail view starts at the top, and returning restores the
  // list where it was, with focus on the job just viewed.
  const prevActiveJobId = useRef(activeJobId);
  useEffect(() => {
    const prev = prevActiveJobId.current;
    prevActiveJobId.current = activeJobId;
    if (activeJobId || !prev) {
      if (activeJobId && !prev && !isDesktop) window.scrollTo({ top: 0 });
      return;
    }
    openedFromList.current = false;
    if (isDesktop) return;
    window.scrollTo({ top: listScrollY.current });
    document.querySelector<HTMLElement>(`a[data-job-id="${CSS.escape(prev)}"]`)?.focus({ preventScroll: true });
  }, [activeJobId, isDesktop]);

  const totalLabel = data ? `${data.total}${data.capped ? "+" : ""} roles` : "Loading…";
  const filtered = hasActiveFilters(filters);

  return (
    <div className="bg-background text-foreground font-sans flex flex-col lg:h-[calc(100dvh-3rem)]">
      {/* Below lg the open job replaces the list, filters included. */}
      <JobFeedToolbar
        className={activeJobId ? "hidden lg:block" : undefined}
        filters={filters}
        onFilter={setFilter}
        totalLabel={totalLabel}
        liveConnected={sseConnected}
        onRefresh={handleRefresh}
        refreshing={isScraping}
      />

      <div className="flex-1 min-h-0 w-full max-w-app mx-auto lg:flex 2xl:border-x border-slate-soft">
        <section
          ref={listPaneRef}
          aria-label="Results"
          className={cn(
            "flex-col lg:flex lg:w-[400px] xl:w-[440px] lg:shrink-0 lg:border-r border-slate-soft lg:overflow-y-auto",
            activeJobId ? "hidden" : "flex",
          )}
        >
          {/* A live region that's always rendered (not display:none), so the
              count is announced when it appears. */}
          <div aria-live="polite" className="flex justify-center not-empty:py-2 not-empty:border-b border-slate-soft">
            {pendingNew > 0 && (
              <button
                type="button"
                onClick={showPendingJobs}
                className="font-mono text-2xs uppercase tracking-wider px-3 py-1.5 rounded-full bg-spruce-green text-warm-ivory shadow-card hover:bg-spruce-green-hover transition-colors"
              >
                ↑ {pendingNew} new {pendingNew === 1 ? "job" : "jobs"}
              </button>
            )}
          </div>

          {isError && (
            <Alert
              variant="error"
              className="m-4"
              action={
                <Button variant="secondary" size="sm" onClick={() => refetch()}>
                  Retry
                </Button>
              }
            >
              {data ? "Couldn't refresh the job list." : "Couldn't load jobs. Check your connection and try again."}
            </Alert>
          )}

          {isLoading ? (
            <>
              <p role="status" className="sr-only">
                Loading jobs
              </p>
              <JobListSkeleton />
            </>
          ) : jobs.length === 0 && !isError ? (
            <EmptyState
              icon={<Briefcase size={22} />}
              title="No positions found"
              description={
                filters.q
                  ? `No job matches for "${filters.q}". Try a different keyword or clear your filters.`
                  : filtered
                    ? "No roles match these filters."
                    : "The board is waiting for the daily crawler or manual refresh."
              }
              action={
                filtered && (
                  <Button variant="secondary" size="sm" onClick={clearFilters}>
                    Clear filters
                  </Button>
                )
              }
            />
          ) : (
            <>
              <JobList
                jobs={jobs}
                activeJobId={activeJobId}
                defaultJobId={defaultJobId}
                jobHref={jobHref}
                onSelect={handleSelect}
                stale={isPlaceholderData}
              />
              {data && (
                <JobListPagination
                  page={filters.page}
                  pages={data.pages}
                  total={data.total}
                  capped={data.capped}
                  onPage={handlePage}
                />
              )}
            </>
          )}
        </section>

        <JobDetailPane
          className={activeJobId ? "flex" : "hidden lg:flex"}
          job={shownJob}
          descriptionLoading={detail.isPlaceholderData || (!detail.data && !detail.isError)}
          loading={isLoading || (!!activeJobId && !shownJob && !detail.isError)}
          unavailable={!!activeJobId && detail.isError && !row}
          onBack={handleBack}
          focusTitleRequestRef={focusTitleRequestRef}
        />
      </div>
    </div>
  );
}
