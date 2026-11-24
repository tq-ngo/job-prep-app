"use client";

import { useCallback, useEffect, useRef, type MouseEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Briefcase } from "lucide-react";
import { Job, JobEvent, JobListResponse, JobSummary } from "@/lib/api";
import { hasActiveFilters, sameFilters, toListParams, type JobFilters } from "@/lib/job-filters";
import { jobQueryKey, useJob, useJobs } from "@/hooks/useJobs";
import { useJobAlerts } from "@/hooks/useJobAlerts";
import { DESKTOP_QUERY, useMediaQuery } from "@/hooks/useMediaQuery";
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

  // ── Continuous live updates ─────────────────────────────────────────────
  // Newly retrieved postings from background crawlers are pushed directly
  // into the feed without requiring manual refresh or showing intrusive alerts.
  // Invalidation is debounced so bursts of newly ingested postings during an
  // active crawl batch coalesce into a single smooth refetch.
  const invalidateTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const { connected: sseConnected } = useJobAlerts({
    onEvent: useCallback(
      (event: JobEvent) => {
        if (event.kind === "created") {
          // Immediately push the newly created job directly into the feed cache
          queryClient.setQueriesData<JobListResponse>({ queryKey: ["jobs"] }, (old) => {
            if (!old) return old;
            if (old.items.some((job) => job.id === event.id)) return old;

            const newJob: JobSummary = {
              id: event.id,
              title: event.title,
              company: event.company,
              company_domain: event.company_domain ?? null,
              location: event.location,
              skills: event.skills ?? [],
              apply_url: event.apply_url,
              source: event.source,
              is_remote: event.is_remote,
              sponsorship_status: event.sponsorship_status ?? null,
              sponsorship_label: event.sponsorship_label ?? null,
              category: event.category ?? null,
              posted_at: event.posted_at ?? null,
              scraped_at: new Date().toISOString(),
              salary_min: event.salary_min ?? null,
              salary_max: event.salary_max ?? null,
              salary_currency: event.salary_currency ?? "USD",
              salary_period: (event.salary_period as "hour" | "year") ?? null,
            };

            return {
              ...old,
              total: old.total + 1,
              items: [newJob, ...old.items],
            };
          });

          if (invalidateTimerRef.current) clearTimeout(invalidateTimerRef.current);
          invalidateTimerRef.current = setTimeout(() => {
            queryClient.invalidateQueries({ queryKey: ["jobs"] });
          }, 300);
        } else if (event.kind === "enriched") {
          // Immediately update enriched attributes (skills) in query cache
          queryClient.setQueriesData<JobListResponse>({ queryKey: ["jobs"] }, (old) => {
            if (!old) return old;
            return {
              ...old,
              items: old.items.map((job) =>
                job.id === event.id ? { ...job, skills: event.skills } : job
              ),
            };
          });
          queryClient.setQueryData<Job>(jobQueryKey(event.id), (old) => {
            if (!old) return old;
            return { ...old, skills: event.skills };
          });
        }
      },
      [queryClient],
    ),
  });

  useEffect(() => {
    return () => {
      if (invalidateTimerRef.current) clearTimeout(invalidateTimerRef.current);
    };
  }, []);

  const listPaneRef = useRef<HTMLElement>(null);
  const scrollListToTop = () => {
    listPaneRef.current?.scrollTo?.({ top: 0 });
    if (!isDesktop) window.scrollTo({ top: 0 });
  };

  const handlePage = (page: number) => {
    setPage(page);
    scrollListToTop();
  };

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
    else closeJob("push"); // deep link: push list state so hardware back navigates within history rather than exiting site
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

  const totalLabel = data
    ? `${data.total}${data.capped ? "+" : ""} roles`
    : isError
      ? "Unavailable"
      : "Loading…";
  const filtered = hasActiveFilters(filters);

  return (
    <div className="bg-surface text-on-surface font-sans flex flex-col lg:h-[calc(100dvh-3rem)]">
      {/* Below lg the open job replaces the list, filters included. */}
      <JobFeedToolbar
        className={activeJobId ? "hidden lg:block" : undefined}
        filters={filters}
        onFilter={setFilter}
        totalLabel={totalLabel}
        liveConnected={sseConnected}
      />

      <div className="flex-1 min-h-0 w-full lg:flex border-t border-outline-variant">
        <section
          ref={listPaneRef}
          aria-label="Results"
          className={cn(
            "flex-col lg:flex lg:w-[400px] xl:w-[440px] lg:shrink-0 lg:border-r border-outline-variant lg:overflow-y-auto",
            activeJobId ? "hidden" : "flex",
          )}
        >
          {isError && !data && (
            <Alert
              variant="error"
              className="m-4"
              action={
                <Button variant="outlined" size="sm" onClick={() => refetch()}>
                  Retry
                </Button>
              }
            >
              Couldn&apos;t load jobs. Check your connection and try again.
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
                    : "The board is waiting for new postings from the background crawlers."
              }
              action={
                filtered && (
                  <Button variant="outlined" size="sm" onClick={clearFilters}>
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
