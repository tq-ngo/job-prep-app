"use client";

import { useEffect, useState } from "react";
import {
  X,
  ExternalLink,
  MapPin,
  Building2,
  Calendar,
  Globe,
  Tag,
  DollarSign,
  Sparkles,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import { Job } from "@/lib/api";

interface JobDetailsSidebarProps {
  job: Job | null;
  onClose: () => void;
}

function CompanyAvatar({ company }: { company: string }) {
  const [imgError, setImgError] = useState(false);
  const cleanDomain = company.toLowerCase().replace(/[^a-z0-9]/g, "") + ".com";
  const initial = company.charAt(0).toUpperCase();

  return (
    <div className="w-12 h-12 rounded-lg border border-slate-soft bg-neutral-soft overflow-hidden flex items-center justify-center shrink-0 shadow-sm">
      {!imgError ? (
        <img
          src={`https://logo.clearbit.com/${cleanDomain}`}
          alt={`${company} logo`}
          className="w-10 h-10 object-contain"
          onError={() => setImgError(true)}
        />
      ) : (
        <div className="w-full h-full bg-gradient-to-br from-spruce-green/20 to-amber-clay/10 flex items-center justify-center font-serif text-lg font-bold text-spruce-green">
          {initial}
        </div>
      )}
    </div>
  );
}

export default function JobDetailsSidebar({
  job,
  onClose,
}: JobDetailsSidebarProps) {
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    if (job) {
      setIsOpen(true);
    } else {
      setIsOpen(false);
    }
  }, [job]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  if (!job) return null;

  return (
    <div className="relative z-50">
      {/* Backdrop */}
      <div
        className={`fixed inset-0 bg-slate-ink/30 backdrop-blur-sm transition-opacity duration-300 ${
          isOpen ? "opacity-100" : "opacity-0 pointer-events-none"
        }`}
        onClick={onClose}
      />

      {/* Slide-over panel */}
      <div
        className={`fixed inset-y-0 right-0 w-full max-w-2xl bg-background shadow-2xl flex flex-col border-l border-slate-soft transform transition-transform duration-300 ease-in-out ${
          isOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {/* Header */}
        <div className="px-6 py-6 border-b border-slate-soft flex justify-between items-start bg-neutral-soft/50">
          <div className="flex items-start gap-4 pr-6 min-w-0">
            <CompanyAvatar company={job.company} />
            <div className="min-w-0">
              <h2
                className="text-xl font-serif font-medium text-slate-ink leading-tight truncate"
                title={job.title}
              >
                {job.title}
              </h2>
              <div className="flex items-center gap-2 text-foreground-muted font-sans text-xs mt-1">
                <span className="font-medium text-slate-ink">
                  {job.company}
                </span>
                <span>•</span>
                <span>
                  {job.location ||
                    (job.is_remote ? "Remote" : "Location Unspecified")}
                </span>
                {job.is_remote && job.location && (
                  <span className="px-1.5 py-0.5 rounded bg-amber-clay/10 text-amber-clay text-[10px] font-mono">
                    Remote
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={onClose}
              className="p-1.5 rounded hover:bg-slate-soft/50 transition-colors text-foreground-subtle hover:text-slate-ink"
              aria-label="Close drawer"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Content (Scrollable) */}
        <div className="flex-1 overflow-y-auto px-6 sm:px-8 py-6 space-y-6">
          {/* Top Action Bar */}
          <div className="flex items-center gap-3">
            <a
              href={job.apply_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 inline-flex items-center justify-center gap-2 py-2.5 px-4 bg-spruce-green hover:bg-spruce-green-hover text-warm-ivory font-sans font-medium text-sm rounded shadow-sm transition-colors"
            >
              Apply on Company Portal <ExternalLink size={14} />
            </a>
          </div>

          {/* Quick Metrics Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="border border-slate-soft rounded p-3 bg-neutral-soft/30">
              <span className="text-[10px] font-mono text-foreground-subtle uppercase tracking-wider block mb-1">
                Source
              </span>
              <span className="text-xs font-mono font-medium text-amber-clay uppercase">
                {job.source}
              </span>
            </div>

            <div className="border border-slate-soft rounded p-3 bg-neutral-soft/30">
              <span className="text-[10px] font-mono text-foreground-subtle uppercase tracking-wider block mb-1">
                Posted
              </span>
              <span className="text-xs font-sans text-slate-ink">
                {job.posted_at
                  ? new Date(job.posted_at).toLocaleDateString(undefined, {
                      month: "short",
                      day: "numeric",
                      year: "numeric",
                    })
                  : "Recently"}
              </span>
            </div>

            <div className="border border-slate-soft rounded p-3 bg-neutral-soft/30">
              <span className="text-[10px] font-mono text-foreground-subtle uppercase tracking-wider block mb-1">
                Status
              </span>
              <span
                className={`text-xs font-sans font-medium ${job.is_active !== false ? "text-spruce-green" : "text-amber-clay"}`}
              >
                {job.is_active !== false ? "Active" : "Closed"}
              </span>
            </div>

            <div className="border border-slate-soft rounded p-3 bg-neutral-soft/30">
              <span className="text-[10px] font-mono text-foreground-subtle uppercase tracking-wider block mb-1">
                Compensation
              </span>
              <span className="text-xs font-sans text-slate-ink truncate block">
                {job.salary_min || job.salary_max
                  ? `$${(job.salary_min || 0).toLocaleString()} ${job.salary_max ? `- $${job.salary_max.toLocaleString()}` : ""}`
                  : "Competitive"}
              </span>
            </div>
          </div>

          {/* Core Skills Badges */}
          {job.skills && job.skills.length > 0 && (
            <div className="border-t border-slate-soft pt-4">
              <h3 className="text-xs font-mono uppercase tracking-wider text-foreground-subtle mb-2.5 flex items-center gap-1.5">
                <Sparkles size={12} className="text-spruce-green" /> Extracted
                Core Skills
              </h3>
              <div className="flex flex-wrap gap-1.5">
                {job.skills.map((skill, i) => (
                  <span
                    key={i}
                    className="px-2.5 py-1 bg-spruce-green/10 text-spruce-green text-xs font-mono rounded border border-spruce-green/20 uppercase tracking-wider"
                  >
                    {skill}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Markdown Job Description */}
          <div className="border-t border-slate-soft pt-4">
            <h3 className="text-xs font-mono uppercase tracking-wider text-foreground-subtle mb-3">
              Job Description
            </h3>

            {job.description ? (
              <div className="text-slate-ink font-sans text-sm leading-relaxed space-y-3 prose-custom">
                <ReactMarkdown
                  components={{
                    h1: ({ ...props }) => (
                      <h1
                        className="text-lg font-serif font-semibold mt-4 mb-2 text-slate-ink"
                        {...props}
                      />
                    ),
                    h2: ({ ...props }) => (
                      <h2
                        className="text-base font-serif font-semibold mt-3 mb-2 text-slate-ink"
                        {...props}
                      />
                    ),
                    h3: ({ ...props }) => (
                      <h3
                        className="text-sm font-serif font-medium mt-3 mb-1 text-slate-ink"
                        {...props}
                      />
                    ),
                    p: ({ ...props }) => (
                      <p
                        className="text-slate-ink/90 mb-2 leading-relaxed"
                        {...props}
                      />
                    ),
                    ul: ({ ...props }) => (
                      <ul
                        className="list-disc list-inside space-y-1 mb-3 text-slate-ink/90 pl-2"
                        {...props}
                      />
                    ),
                    ol: ({ ...props }) => (
                      <ol
                        className="list-decimal list-inside space-y-1 mb-3 text-slate-ink/90 pl-2"
                        {...props}
                      />
                    ),
                    li: ({ ...props }) => (
                      <li className="text-slate-ink/90" {...props} />
                    ),
                    strong: ({ ...props }) => (
                      <strong
                        className="font-semibold text-slate-ink"
                        {...props}
                      />
                    ),
                    code: ({ ...props }) => (
                      <code
                        className="bg-neutral-soft px-1.5 py-0.5 rounded font-mono text-xs text-spruce-green"
                        {...props}
                      />
                    ),
                  }}
                >
                  {job.description}
                </ReactMarkdown>
              </div>
            ) : (
              <div className="py-12 text-center border border-dashed border-slate-soft rounded p-8">
                <p className="font-sans text-sm text-foreground-muted mb-3">
                  Direct description content not yet mirrored from {job.source}.
                </p>
                <a
                  href={job.apply_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-xs font-medium text-spruce-green hover:underline"
                >
                  View full posting on external site <ExternalLink size={12} />
                </a>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
