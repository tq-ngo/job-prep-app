"use client";

import { useEffect, useId, useRef, type RefObject } from "react";
import dynamic from "next/dynamic";
import { ArrowLeft, Briefcase, ExternalLink, SearchX, Sparkles } from "lucide-react";
import type { Job, JobSummary } from "@/lib/api";
import { formatDate, formatLocation, formatPay } from "@/lib/format";
import { getJobSponsorship } from "@/lib/sponsorship";
import Badge from "@/components/ui/Badge";
import { Button, ButtonLink } from "@/components/ui/Button";
import { cn } from "@/components/ui/cn";
import EmptyState from "@/components/ui/EmptyState";
import Skeleton, { SkeletonGroup } from "@/components/ui/Skeleton";
import CompanyAvatar from "./CompanyAvatar";

function DescriptionSkeleton() {
  return (
    <SkeletonGroup label="Loading description" className="space-y-2.5">
      {[100, 92, 96, 70, 88, 60].map((w, i) => (
        <Skeleton key={i} className="h-3" style={{ width: `${w}%` }} />
      ))}
    </SkeletonGroup>
  );
}

const JobDescription = dynamic(() => import("./JobDescription"), { loading: DescriptionSkeleton });

interface JobDetailPaneProps {
  /** The job to show: the full job, or the list row while it loads. */
  job: Job | JobSummary | null;
  /** The full job (description) is still loading. */
  descriptionLoading: boolean;
  /** Nothing to show yet (first load, or a deep link still fetching). */
  loading: boolean;
  /** The selected job couldn't be loaded (removed, or a bad link). */
  unavailable: boolean;
  /** "Back to results" on small screens, where the pane replaces the list. */
  onBack: () => void;
  /**
   * Set before a selection change to move focus to the title once the new
   * job renders: on keyboard selection and on mobile, never for mouse users
   * browsing the list on desktop.
   */
  focusTitleRequestRef: RefObject<boolean>;
  className?: string;
}

/**
 * The selected job's details, beside the list on desktop and in its place on
 * mobile. Not a dialog: no focus trap or scroll lock, it's part of the page.
 */
export default function JobDetailPane({
  job,
  descriptionLoading,
  loading,
  unavailable,
  onBack,
  focusTitleRequestRef,
  className,
}: JobDetailPaneProps) {
  const titleId = useId();
  const paneRef = useRef<HTMLElement>(null);
  const titleRef = useRef<HTMLHeadingElement>(null);
  const jobId = job?.id;

  // A new job starts at its top, and takes focus when asked to.
  useEffect(() => {
    if (!jobId) return;
    paneRef.current?.scrollTo?.({ top: 0 });
    if (focusTitleRequestRef.current) {
      focusTitleRequestRef.current = false;
      titleRef.current?.focus({ preventScroll: true });
    }
  }, [jobId, focusTitleRequestRef]);

  const backButton = (
    <Button variant="ghost" size="sm" onClick={onBack} icon={<ArrowLeft size={14} aria-hidden="true" />} className="lg:hidden -ml-2">
      Back to results
    </Button>
  );

  if (!job) {
    return (
      <section ref={paneRef} aria-label="Job details" className={cn("flex-col min-w-0 lg:flex-1 lg:overflow-y-auto", className)}>
        <div className="px-4 pt-3 lg:hidden">{backButton}</div>
        {loading ? (
          <DetailSkeleton />
        ) : unavailable ? (
          <EmptyState
            icon={<SearchX size={22} />}
            title="This job isn't available"
            description="It may have been removed or filled. Pick another role from the list."
          />
        ) : (
          <EmptyState icon={<Briefcase size={22} />} title="No job selected" description="Pick a role from the list to see its details." />
        )}
      </section>
    );
  }

  const description = "description" in job ? job.description : null;
  const sponsorship = getJobSponsorship(job);

  const metrics = [
    { label: "Source", value: <span className="font-mono uppercase text-amber-clay">{job.source}</span> },
    { label: "Posted", value: job.posted_at ? formatDate(job.posted_at) : "Unknown" },
    {
      label: "Status",
      value: (
        <span className={job.is_active !== false ? "text-spruce-green" : "text-amber-clay"}>
          {job.is_active !== false ? "Active" : "Closed"}
        </span>
      ),
    },
    { label: "Compensation", value: formatPay(job) ?? "Not listed" },
    {
      label: "Visa / Work Auth",
      value: (
        <span className={sponsorship.isCitizenOnly ? "text-amber-clay font-medium" : "text-spruce-green font-medium"}>
          {sponsorship.label}
        </span>
      ),
    },
  ];

  return (
    <section ref={paneRef} aria-labelledby={titleId} className={cn("flex-col min-w-0 lg:flex-1 lg:overflow-y-auto", className)}>
      <header className="sticky top-12 lg:top-0 z-10 bg-background/95 backdrop-blur-md border-b border-slate-soft px-4 sm:px-6 lg:px-8 py-4 shadow-xs">
        <div className="mb-2 lg:hidden">{backButton}</div>
        <div className="flex items-start gap-4">
          <CompanyAvatar company={job.company} size="lg" />
          <div className="min-w-0 flex-1">
            <h2 id={titleId} ref={titleRef} tabIndex={-1} className="text-xl font-serif font-medium text-slate-ink leading-tight">
              {job.title}
            </h2>
            <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-foreground-muted font-sans text-xs mt-1.5">
              <span className="font-medium text-slate-ink">{job.company}</span>
              <span aria-hidden="true">•</span>
              <span>{formatLocation(job)}</span>
              {job.is_remote && job.location && <Badge variant="remote">Remote</Badge>}
              <Badge variant={sponsorship.isCitizenOnly ? "citizenship" : "sponsorship"}>
                {sponsorship.label}
              </Badge>
            </p>
          </div>
          <ButtonLink href={job.apply_url} external size="sm" className="shrink-0 rounded-full px-4 shadow-xs">
            Apply <ExternalLink size={13} aria-hidden="true" />
          </ButtonLink>
        </div>
      </header>

      {/* Capped at a readable line length; the pane is ~1000px wide on desktop. */}
      <div className="max-w-3xl px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        <dl className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          {metrics.map(({ label, value }) => (
            <div key={label} className="border border-slate-soft/80 rounded-xl p-3.5 bg-neutral-soft shadow-xs">
              <dt className="text-2xs font-mono text-foreground-subtle uppercase tracking-wider mb-1">{label}</dt>
              <dd className="text-xs font-sans font-medium text-slate-ink truncate">{value}</dd>
            </div>
          ))}
        </dl>

        {job.skills && job.skills.length > 0 && (
          <section className="border-t border-slate-soft pt-4">
            <h3 className="text-xs font-mono uppercase tracking-wider text-foreground-subtle mb-2.5 flex items-center gap-1.5">
              <Sparkles size={12} aria-hidden="true" className="text-spruce-green" /> Extracted skills
            </h3>
            <ul className="flex flex-wrap gap-1.5">
              {job.skills.map((skill) => (
                <li key={skill}>
                  <Badge variant="skill" size="md">
                    {skill}
                  </Badge>
                </li>
              ))}
            </ul>
          </section>
        )}

        <section className="border-t border-slate-soft pt-4">
          <h3 className="text-xs font-mono uppercase tracking-wider text-foreground-subtle mb-3">Job description</h3>
          {descriptionLoading ? (
            <DescriptionSkeleton />
          ) : description ? (
            <JobDescription markdown={description} />
          ) : (
            <div className="py-10 text-center border border-dashed border-slate-soft rounded-2xl p-8 bg-neutral-soft/40">
              <p className="font-sans text-sm text-foreground-muted mb-3">The full description isn&apos;t available here yet.</p>
              <a
                href={job.apply_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-xs font-medium text-spruce-green hover:underline"
              >
                View the posting on the company site <ExternalLink size={12} aria-hidden="true" />
              </a>
            </div>
          )}
        </section>
      </div>
    </section>
  );
}

function DetailSkeleton() {
  return (
    <SkeletonGroup label="Loading job" className="px-4 sm:px-6 lg:px-8 py-4 space-y-6">
      <div className="flex gap-4">
        <Skeleton className="w-12 h-12" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-5 w-2/3" />
          <Skeleton className="h-3 w-1/3" />
        </div>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-14" />
        ))}
      </div>
      <Skeleton className="h-40" />
    </SkeletonGroup>
  );
}
