"use client";

import type { KeyboardEvent, MouseEvent } from "react";
import type { JobSummary } from "@/lib/api";
import { usePrefetchJob } from "@/hooks/useJobs";
import Skeleton from "@/components/ui/Skeleton";
import JobListItem from "./JobListItem";

interface JobListProps {
  jobs: JobSummary[];
  /** Explicitly selected job (?jobId=). */
  activeJobId: string | null;
  /** Job shown by default when none is selected (desktop), else null. */
  defaultJobId: string | null;
  jobHref: (id: string) => string;
  onSelect: (job: JobSummary, e: MouseEvent<HTMLAnchorElement>) => void;
  /** Rows are the previous page/filter's while the new ones load. */
  stale?: boolean;
}

const KEYS = ["ArrowDown", "ArrowUp", "Home", "End"];

/**
 * The results list. One item is in the tab order (the selected one, else the
 * first), so Tab moves past 30 results in one step; arrow keys, Home and End
 * move between items.
 */
export default function JobList({ jobs, activeJobId, defaultJobId, jobHref, onSelect, stale }: JobListProps) {
  const prefetchJob = usePrefetchJob();
  const tabbableId = jobs.some((j) => j.id === activeJobId) ? activeJobId : jobs[0]?.id;

  const handleKeyDown = (e: KeyboardEvent<HTMLUListElement>) => {
    if (!KEYS.includes(e.key)) return;
    const links = Array.from(e.currentTarget.querySelectorAll<HTMLAnchorElement>("a[data-job-link]"));
    const i = links.indexOf(document.activeElement as HTMLAnchorElement);
    if (i < 0) return;
    e.preventDefault();
    const next =
      e.key === "Home" ? 0 : e.key === "End" ? links.length - 1 : e.key === "ArrowDown" ? Math.min(i + 1, links.length - 1) : Math.max(i - 1, 0);
    links[next].focus();
  };

  return (
    <ul
      aria-label="Job results"
      aria-busy={stale || undefined}
      onKeyDown={handleKeyDown}
      className={`divide-y divide-slate-soft transition-opacity ${stale ? "opacity-60" : ""}`}
    >
      {jobs.map((job) => (
        <JobListItem
          key={job.id}
          job={job}
          href={jobHref(job.id)}
          selected={job.id === activeJobId}
          defaultSelected={job.id === defaultJobId}
          tabbable={job.id === tabbableId}
          onSelect={onSelect}
          onPrefetch={prefetchJob}
        />
      ))}
    </ul>
  );
}

/** Placeholder rows for the first load (aria-hidden; the feed announces loading). */
export function JobListSkeleton({ rows = 8 }: { rows?: number }) {
  return (
    <div aria-hidden="true" className="divide-y divide-slate-soft">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="flex gap-3 px-4 py-3">
          <Skeleton className="w-10 h-10 shrink-0" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-3.5 w-3/4" />
            <Skeleton className="h-3 w-1/3" />
            <Skeleton className="h-3 w-1/2" />
          </div>
        </div>
      ))}
    </div>
  );
}
