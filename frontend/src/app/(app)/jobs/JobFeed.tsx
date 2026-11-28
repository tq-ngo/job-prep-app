"use client";

import { useCallback, useEffect, useRef, useState, type MouseEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Briefcase } from "lucide-react";
import { Job, JobEvent, JobListResponse, JobSummary } from "@/lib/api";
import { hasActiveFilters, sameFilters, toListParams, type JobFilters, type JobListParams } from "@/lib/job-filters";
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

const MAX_DISPLAY_TOTAL = 500;

function isUnfilteredDatePageOne(params: JobListParams | undefined): boolean {
  if (!params) return false;
  return (
    (params.page ?? 1) === 1 &&
    !params.q &&
    !params.category &&
    !params.source &&
    !params.work_type &&
    !params.sponsorship &&
    !params.skill &&
    !params.is_remote &&
    (!params.sort_by || params.sort_by === "date")
  );
}

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
 */
export default function JobFeed({ initialData, initialDataUpdatedAt, initialFilters }: JobFeedProps) {
  const { filters, activeJobId, setFilter, clearFilters, setPage, jobHref, openJob, closeJob } = useJobFeedUrlState();
  const isDesktop = useMediaQuery(DESKTOP_QUERY);
  const queryClient = useQueryClient();

  // The server seeded exactly one filter set; only that query may use it.
  const seeded = initialData && initialFilters && sameFilters(initialFilters, filters);
  const listParams = toListParams(filters);
  const jobsQuery = useJobs(listParams, seeded ? { initialData, initialDataUpdatedAt } : {});
  const { data, isLoading, isError, isPlaceholderData, refetch } = jobsQuery;
  const jobs = data?.items ?? [];

  // ── Continuous live updates ─────────────────────────────────────────────
  // Newly retrieved postings from background crawlers are pushed directly
  // into unfiltered page-1 feeds without manual refreshes or alert popups.
  const invalidateTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const { connected: sseConnected } = useJobAlerts({
    onEvent: useCallback(
      (event: JobEvent) => {
        if (event.kind === "created") {
          // Only optimistically prepend into unfiltered, page-1, date-sorted queries
          // so filtered views or deeper pages never receive mismatched rows.
          queryClient.setQueriesData<JobListResponse>(
            {
              queryKey: ["jobs"],
              predicate: (query) => isUnfilteredDatePageOne(query.queryKey[1] as JobListParams | undefined),
            },
            (old) => {
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

              const hitCap = Boolean(old.capped) || old.total >= MAX_DISPLAY_TOTAL;
              const nextTotal = hitCap ? Math.min(old.total, MAX_DISPLAY_TOTAL) : old.total + 1;
              const maxItems = old.page_size || old.items.length + 1;

              return {
                ...old,
                total: nextTotal,
                capped: hitCap || nextTotal >= MAX_DISPLAY_TOTAL ? true : old.capped,
                items: [newJob, ...old.items].slice(0, maxItems),
              };
            },
          );

          if (invalidateTimerRef.current) clearTimeout(invalidateTimerRef.current);
          invalidateTimerRef.current = setTimeout(() => {
            queryClient.invalidateQueries({ queryKey: ["jobs"] });
          }, 300);
        } else if (event.kind === "enriched") {
          const patch = {
            skills: event.skills,
            ...(event.location !== undefined ? { location: event.location } : {}),
            ...(event.is_remote !== undefined ? { is_remote: event.is_remote } : {}),
            ...(event.sponsorship_status !== undefined ? { sponsorship_status: event.sponsorship_status } : {}),
            ...(event.sponsorship_label !== undefined ? { sponsorship_label: event.sponsorship_label } : {}),
            ...(event.category !== undefined ? { category: event.category } : {}),
            ...(event.salary_min !== undefined ? { salary_min: event.salary_min } : {}),
            ...(event.salary_max !== undefined ? { salary_max: event.salary_max } : {}),
            ...(event.salary_currency !== undefined ? { salary_currency: event.salary_currency } : {}),
            ...(event.salary_period !== undefined
              ? { salary_period: (event.salary_period as "hour" | "year" | null) ?? null }
              : {}),
          };

          queryClient.setQueriesData<JobListResponse>({ queryKey: ["jobs"] }, (old) => {
            if (!old) return old;
            return {
              ...old,
              items: old.items.map((job) => (job.id === event.id ? { ...job, ...patch } : job)),
            };
          });
          queryClient.setQueryData<Job>(jobQueryKey(event.id), (old) => {
            if (!old) return old;
            return { ...old, ...patch };
          });
          queryClient.invalidateQueries({ queryKey: jobQueryKey(event.id) });
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
  // With nothing selected, desktop shows the first result without writing to
  // the URL. Pin that default id per filter/page signature so an SSE prepend
  // doesn't yank the reader out of the description they're currently viewing.
  const filterSignature = JSON.stringify(listParams);
  const [pinnedDefault, setPinnedDefault] = useState<{ sig: string; id: string | null }>({
    sig: filterSignature,
    id: jobs[0]?.id ?? null,
  });

  const firstJobId = jobs[0]?.id ?? null;
  const pinnedStillVisible =
    pinnedDefault.sig === filterSignature &&
    pinnedDefault.id !== null &&
    jobs.some((j) => j.id === pinnedDefault.id);

  const stableFirstId = pinnedStillVisible ? pinnedDefault.id : firstJobId;

  useEffect(() => {
    if (pinnedDefault.sig !== filterSignature || (!pinnedStillVisible && pinnedDefault.id !== firstJobId)) {
      setPinnedDefault({ sig: filterSignature, id: firstJobId });
    }
  }, [filterSignature, firstJobId, pinnedDefault.id, pinnedDefault.sig, pinnedStillVisible]);

  const defaultJobId = !activeJobId && isDesktop ? stableFirstId : null;
  const shownId = activeJobId ?? stableFirstId;
  const row = jobs.find((j) => j.id === shownId);
  const detail = useJob(activeJobId ?? defaultJobId, row);
  const shownJob = detail.data ?? row ?? null;

  const focusTitleRequestRef = useRef(false);
  const listScrollY = useRef(0);
  const openedFromList = useRef(false);

  const handleSelect = (job: JobSummary, e: MouseEvent<HTMLAnchorElement>) => {
    focusTitleRequestRef.current = e.detail === 0 || !isDesktop;
    listScrollY.current = window.scrollY;
    openedFromList.current = true;
    openJob(job.id);
  };

  const handleBack = () => {
    if (openedFromList.current) window.history.back();
    else closeJob("push");
  };

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
    <div className="bg-surface text-on-surface font-sans flex flex-col lg:h-[calc(100dvh-3.5rem)]">
      {/* Keep a page-level h1 in the accessibility tree when mobile replaces the toolbar with the detail pane. */}
      {activeJobId && <h1 className="sr-only lg:hidden">Job Board</h1>}

      <JobFeedToolbar
        className={activeJobId ? "hidden lg:block" : undefined}
        filters={filters}
        onFilter={setFilter}
        onClearAll={clearFilters}
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
          {isError && (
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
              icon={<Briefcase size={20} strokeWidth={1.5} />}
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
