"use client";

import type { MouseEvent } from "react";
import type { JobSummary } from "@/lib/api";
import { formatLocation, formatPay, formatPostedAgo } from "@/lib/format";
import Badge from "@/components/ui/Badge";
import { cn } from "@/components/ui/cn";
import CompanyAvatar from "./CompanyAvatar";

interface JobListItemProps {
  job: JobSummary;
  href: string;
  /** Selected via the URL (?jobId=). */
  selected: boolean;
  /** Shown in the detail pane by default (first result, desktop only). */
  defaultSelected: boolean;
  /** The one item in the list's tab order (roving focus). */
  tabbable: boolean;
  onSelect: (job: JobSummary, e: MouseEvent<HTMLAnchorElement>) => void;
  onPrefetch: (id: string) => void;
}

/**
 * A real link, so middle-click and "open in new tab" work. A plain click
 * is intercepted and handled in place (see JobFeed's onSelect).
 */
export default function JobListItem({
  job,
  href,
  selected,
  defaultSelected,
  tabbable,
  onSelect,
  onPrefetch,
}: JobListItemProps) {
  const pay = formatPay(job);
  const skills = job.skills?.slice(0, 3) ?? [];

  const handleClick = (e: MouseEvent<HTMLAnchorElement>) => {
    // Let the browser handle new-tab/new-window gestures.
    if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    onSelect(job, e);
  };

  return (
    <li>
      <a
        href={href}
        data-job-link
        data-job-id={job.id}
        tabIndex={tabbable ? 0 : -1}
        aria-current={selected || defaultSelected ? "true" : undefined}
        onClick={handleClick}
        onMouseEnter={() => onPrefetch(job.id)}
        onFocus={() => onPrefetch(job.id)}
        className={cn(
          "group flex gap-3 px-4 py-3.5 border-l-4 transition-all duration-150 hover:bg-neutral-soft -outline-offset-2",
          selected || defaultSelected
            ? "border-l-spruce-green bg-spruce-green/8 shadow-xs"
            : "border-l-transparent",
        )}
      >
        <CompanyAvatar company={job.company} />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-slate-ink leading-snug line-clamp-2 group-hover:text-spruce-green transition-colors">
            {job.title}
          </p>
          <p className="mt-0.5 text-xs text-foreground-muted truncate">{job.company}</p>
          <p className="text-xs text-foreground-subtle truncate">{formatLocation(job, "—")}</p>

          {(pay || job.is_remote) && (
            <p className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-foreground">
              {pay}
              {job.is_remote && job.location && <Badge variant="remote">Remote</Badge>}
            </p>
          )}

          {skills.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {skills.map((skill) => (
                <Badge key={skill} variant="skill">
                  {skill}
                </Badge>
              ))}
            </div>
          )}

          <p className="mt-2 flex items-center gap-2 font-mono text-2xs text-foreground-subtle">
            <Badge variant="source">{job.source}</Badge>
            {job.posted_at && (
              // Relative to now, so it can differ by a day between the server
              // render and hydration around midnight.
              <time dateTime={job.posted_at} suppressHydrationWarning>
                {formatPostedAgo(job.posted_at)}
              </time>
            )}
          </p>
        </div>
      </a>
    </li>
  );
}
