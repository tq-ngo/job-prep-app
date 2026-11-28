"use client";

import type { MouseEvent } from "react";
import type { JobSummary } from "@/lib/api";
import { formatLocation, formatPay, formatPostedAgo } from "@/lib/format";
import { getJobSponsorship } from "@/lib/sponsorship";
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
  const skills = job.skills?.slice(0, 3) ?? [];
  const sponsorship = getJobSponsorship(job);
  const pay = formatPay(job);

  const handleClick = (e: MouseEvent<HTMLAnchorElement>) => {
    // Let the browser handle new-tab/new-window gestures.
    if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    onSelect(job, e);
  };

  const isActive = selected || defaultSelected;

  return (
    <li>
      <a
        href={href}
        data-job-link
        data-job-id={job.id}
        tabIndex={tabbable ? 0 : -1}
        aria-current={isActive ? "true" : undefined}
        onClick={handleClick}
        onMouseEnter={() => onPrefetch(job.id)}
        onFocus={() => onPrefetch(job.id)}
        className={cn(
          "group flex gap-3 px-4 py-4 border-l-4 transition-colors duration-150 -outline-offset-2",
          isActive
            ? "border-l-primary bg-secondary-container"
            : "border-l-transparent hover:bg-on-surface/8 focus-visible:bg-on-surface/12",
        )}
      >
        <CompanyAvatar company={job.company} companyDomain={job.company_domain} />
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <p
              className={cn(
                "text-title-small font-medium leading-snug line-clamp-2 transition-colors",
                isActive ? "text-on-secondary-container" : "text-on-surface group-hover:text-primary",
              )}
            >
              {job.title}
            </p>
            {pay && (
              <span
                className={cn(
                  "shrink-0 font-mono text-label-small font-medium tabular-nums",
                  isActive ? "text-on-secondary-container" : "text-on-surface",
                )}
              >
                {pay}
              </span>
            )}
          </div>
          <p className={cn("mt-0.5 text-body-small truncate", isActive ? "text-on-secondary-container" : "text-on-surface-variant")}>
            {job.company}
          </p>
          <p className={cn("text-body-small truncate", isActive ? "text-on-secondary-container" : "text-on-surface-variant")}>
            {formatLocation(job, "—")}
          </p>

          {(job.is_remote || sponsorship?.label) && (
            <p className="mt-2 flex flex-wrap items-center gap-1.5">
              {job.is_remote && job.location && <Badge variant="remote">Remote</Badge>}
              {sponsorship?.label && (
                <Badge
                  variant={
                    sponsorship.status === "citizenship"
                      ? "citizenship"
                      : sponsorship.status === "no_sponsorship"
                        ? "no_sponsorship"
                        : "sponsorship"
                  }
                >
                  {sponsorship.label}
                </Badge>
              )}
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

          {job.posted_at && (
            <p
              className={cn(
                "mt-2 flex items-center font-mono text-label-small tabular-nums",
                isActive ? "text-on-secondary-container" : "text-on-surface-variant",
              )}
            >
              <time dateTime={job.posted_at} suppressHydrationWarning>
                {formatPostedAgo(job.posted_at)}
              </time>
            </p>
          )}
        </div>
      </a>
    </li>
  );
}
