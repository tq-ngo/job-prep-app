"use client";

import { useEffect, useId, useRef, type RefObject } from "react";
import dynamic from "next/dynamic";
import { ArrowLeft, Briefcase, ExternalLink, SearchX } from "lucide-react";
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
    <Button
      variant="text"
      size="sm"
      onClick={onBack}
      icon={<ArrowLeft size={16} strokeWidth={1.5} aria-hidden="true" />}
      className="lg:hidden -ml-2"
    >
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
            icon={<SearchX size={20} strokeWidth={1.5} />}
            title="This job isn't available"
            description="It may have been removed or filled. Pick another role from the list."
          />
        ) : (
          <EmptyState icon={<Briefcase size={20} strokeWidth={1.5} />} title="No job selected" description="Pick a role from the list to see its details." />
        )}
      </section>
    );
  }

  const description = "description" in job ? job.description : null;
  const sponsorship = getJobSponsorship(job);
  const pay = formatPay(job);

  const workType =
    job.work_type === "remote" || job.is_remote
      ? "Remote"
      : job.work_type === "hybrid"
        ? "Hybrid"
        : job.work_type === "onsite"
          ? "On-site"
          : job.location?.toLowerCase().includes("remote")
            ? "Remote"
            : job.location?.toLowerCase().includes("hybrid")
              ? "Hybrid"
              : "On-site";

  const metrics = [
    ...(pay
      ? [
          {
            label: "Compensation",
            value: <span className="font-mono font-medium text-on-surface tabular-nums">{pay}</span>,
          },
        ]
      : []),
    {
      label: "Work type",
      value: <span className="font-sans font-medium text-on-surface">{workType}</span>,
    },
    {
      label: "Posted",
      value: <span className="font-mono tabular-nums">{job.posted_at ? formatDate(job.posted_at) : "Unknown"}</span>,
    },
    {
      label: "Status",
      value: (
        <span className={job.is_active !== false ? "text-primary" : "text-error"}>
          {job.is_active !== false ? "Active" : "Closed"}
        </span>
      ),
    },
    {
      label: "Visa / work auth",
      value: sponsorship?.label ? (
        <span
          className={
            sponsorship.status === "citizenship" || sponsorship.status === "no_sponsorship"
              ? "text-error font-medium"
              : "text-primary font-medium"
          }
        >
          {sponsorship.label}
        </span>
      ) : (
        <span className="text-on-surface-variant">Not specified</span>
      ),
    },
  ];

  return (
    <section
      ref={paneRef}
      aria-labelledby={titleId}
      className={cn("flex-col min-w-0 lg:flex-1 lg:overflow-y-auto bg-surface-container-low/40", className)}
    >
      <header className="sticky top-14 lg:top-0 z-10 bg-surface-container-lowest/95 dark:bg-surface-container-low/95 backdrop-blur-md border-b border-outline-variant px-4 sm:px-6 lg:px-8 py-4">
        <div className="mb-2 lg:hidden">{backButton}</div>
        <div className="flex items-start gap-4">
          <CompanyAvatar company={job.company} companyDomain={job.company_domain} size="lg" />
          <div className="min-w-0 flex-1">
            <h2 id={titleId} ref={titleRef} tabIndex={-1} className="text-headline-small font-semibold text-on-surface leading-tight">
              {job.title}
            </h2>
            <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-on-surface-variant font-sans text-body-small mt-1.5">
              <span className="font-medium text-on-surface">{job.company}</span>
              <span aria-hidden="true">·</span>
              <span>{formatLocation(job)}</span>
              {pay && (
                <>
                  <span aria-hidden="true">·</span>
                  <span className="font-mono font-medium text-on-surface tabular-nums">{pay}</span>
                </>
              )}
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
          </div>
          <ButtonLink href={job.apply_url} external variant="filled" size="sm" className="shrink-0 px-5">
            <span>Apply</span>
            <ExternalLink size={14} strokeWidth={1.5} aria-hidden="true" />
          </ButtonLink>
        </div>
      </header>

      <div className="w-full px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        <dl
          className={cn(
            "grid grid-cols-2 gap-4",
            metrics.length >= 5 ? "sm:grid-cols-3 xl:grid-cols-5" : "sm:grid-cols-4",
          )}
        >
          {metrics.map(({ label, value }) => (
            <div
              key={label}
              className="border border-outline-variant rounded-md p-4 bg-surface-container-lowest dark:bg-surface-container-low"
            >
              <dt className="text-label-small font-mono text-on-surface-variant mb-1">{label}</dt>
              <dd className="text-body-small font-sans font-medium text-on-surface truncate">{value}</dd>
            </div>
          ))}
        </dl>

        {job.skills && job.skills.length > 0 && (
          <section className="border-t border-outline-variant pt-4">
            <h3 className="text-label-medium font-medium text-on-surface-variant mb-3">Extracted skills</h3>
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

        <section className="border-t border-outline-variant pt-4">
          <h3 className="text-label-medium font-medium text-on-surface-variant mb-3">Job description</h3>
          {descriptionLoading ? (
            <DescriptionSkeleton />
          ) : description ? (
            <div className="rounded-lg border border-outline-variant bg-surface-container-lowest dark:bg-surface-container-low p-6">
              <JobDescription markdown={description} />
            </div>
          ) : (
            <div className="py-10 text-center border border-dashed border-outline-variant rounded-lg p-8 bg-surface-container-low">
              <p className="font-sans text-body-medium text-on-surface-variant mb-3">The full description isn&apos;t available here yet.</p>
              <a
                href={job.apply_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-label-medium font-medium text-primary hover:underline"
              >
                View the posting on the company site <ExternalLink size={14} strokeWidth={1.5} aria-hidden="true" />
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
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-14" />
        ))}
      </div>
      <Skeleton className="h-40" />
    </SkeletonGroup>
  );
}
