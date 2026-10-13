"use client";

import { useEffect, useId, useRef, useState } from "react";
import { X, ExternalLink, Sparkles } from "lucide-react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { Job } from "@/lib/api";

interface JobDetailsSidebarProps {
  /** The job to show; null while a deep-linked job is still loading. */
  job: Job | null;
  /** False plays the exit transition; the panel stays mounted but inert. */
  open: boolean;
  /** True while only the feed row is known and the description is loading. */
  isLoadingDescription?: boolean;
  onClose: () => void;
}

/**
 * Initials avatar. This used to request `logo.clearbit.com/<guess>.com`
 * on every open: a third-party call that leaked viewers' IPs and the roles
 * they browsed, and whose domain guess was wrong for most multi-word names.
 */
function CompanyAvatar({ company }: { company: string }) {
  const initials = company
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase())
    .join("");
  return (
    <div
      aria-hidden="true"
      className="w-11 h-11 rounded-lg border border-slate-soft bg-gradient-to-br from-spruce-green/20 to-amber-clay/10 flex items-center justify-center shrink-0 font-serif text-base font-semibold text-spruce-green"
    >
      {initials || "?"}
    </div>
  );
}

// Styles for every element markdownify emits from a sanitized JD. Tables
// render only because of remark-gfm: without it, GFM pipe tables showed up
// as literal "| a | b |" text.
const markdownComponents: Components = {
  h1: (props) => <h3 className="text-lg font-serif font-semibold mt-5 mb-2 text-slate-ink" {...props} />,
  h2: (props) => <h3 className="text-base font-serif font-semibold mt-4 mb-2 text-slate-ink" {...props} />,
  h3: (props) => <h4 className="text-sm font-serif font-semibold mt-4 mb-1.5 text-slate-ink" {...props} />,
  h4: (props) => <h5 className="text-sm font-sans font-semibold mt-3 mb-1 text-slate-ink" {...props} />,
  h5: (props) => <h6 className="text-sm font-sans font-medium mt-3 mb-1 text-slate-ink" {...props} />,
  h6: (props) => <h6 className="text-xs font-sans font-semibold uppercase tracking-wider mt-3 mb-1 text-foreground-muted" {...props} />,
  p: (props) => <p className="mb-3 leading-relaxed" {...props} />,
  // list-outside + padding keeps wrapped bullet text aligned under the text,
  // not under the marker (list-inside broke that).
  ul: (props) => <ul className="list-disc list-outside pl-5 space-y-1 mb-3" {...props} />,
  ol: (props) => <ol className="list-decimal list-outside pl-5 space-y-1 mb-3" {...props} />,
  li: (props) => <li className="pl-0.5" {...props} />,
  strong: (props) => <strong className="font-semibold text-slate-ink" {...props} />,
  blockquote: (props) => (
    <blockquote className="border-l-2 border-spruce-green/40 pl-3 my-3 text-foreground-muted italic" {...props} />
  ),
  hr: () => <hr className="my-4 border-slate-soft" />,
  a: ({ href, ...props }) => (
    <a href={href} target="_blank" rel="noopener noreferrer nofollow" className="text-spruce-green underline underline-offset-2" {...props} />
  ),
  code: (props) => <code className="bg-neutral-soft px-1.5 py-0.5 rounded font-mono text-xs text-spruce-green" {...props} />,
  pre: (props) => <pre className="bg-neutral-soft p-3 rounded overflow-x-auto text-xs mb-3" {...props} />,
  table: (props) => (
    <div className="overflow-x-auto mb-3">
      <table className="w-full text-xs border-collapse border border-slate-soft" {...props} />
    </div>
  ),
  th: (props) => <th className="border border-slate-soft bg-neutral-soft px-2 py-1 text-left font-semibold" {...props} />,
  td: (props) => <td className="border border-slate-soft px-2 py-1 align-top" {...props} />,
};

function formatPay(job: Job): string {
  const { salary_min: lo, salary_max: hi, salary_period: period } = job;
  if (!lo && !hi) return "Not listed";
  const fmt = (n: number) => `$${n.toLocaleString("en-US")}`;
  const range = lo && hi && lo !== hi ? `${fmt(lo)} – ${fmt(hi)}` : fmt((lo || hi)!);
  return period === "hour" ? `${range}/hr` : period === "year" ? `${range}/yr` : range;
}

const FOCUSABLE =
  'a[href], button:not([disabled]), input, select, textarea, [tabindex]:not([tabindex="-1"])';

export default function JobDetailsSidebar({
  job,
  open,
  isLoadingDescription = false,
  onClose,
}: JobDetailsSidebarProps) {
  const titleId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  // Keep showing the last job while the exit transition plays; the drawer
  // used to unmount the instant `job` became null, so it never animated out.
  // (setState during render is React's sanctioned "derive from props" path.)
  const [shown, setShown] = useState<Job | null>(job);
  if (job && job !== shown) setShown(job);

  // Focus management: move focus into the dialog on open, trap Tab inside
  // it, close on Escape, and hand focus back to the opener on close.
  useEffect(() => {
    if (!open) return;
    const opener = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
        return;
      }
      if (e.key !== "Tab" || !panelRef.current) return;
      const items = Array.from(panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = prevOverflow;
      opener?.focus?.();
    };
  }, [open, onClose]);

  const view = shown;

  return (
    <div className="relative z-50" inert={!open}>
      {/* Backdrop */}
      <div
        aria-hidden="true"
        className={`fixed inset-0 bg-slate-ink/30 backdrop-blur-sm transition-[opacity,visibility] duration-300 starting:opacity-0 ${
          open ? "opacity-100 visible" : "opacity-0 invisible"
        }`}
        onClick={onClose}
      />

      {/* Slide-over panel. `starting:` (@starting-style) animates the entry
          without an effect that flips state after mount. */}
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className={`fixed inset-y-0 right-0 w-full max-w-2xl bg-background shadow-2xl flex flex-col border-l border-slate-soft transition-[translate,visibility] duration-300 ease-in-out starting:translate-x-full ${
          open ? "translate-x-0 visible" : "translate-x-full invisible"
        }`}
      >
        {/* Header */}
        <div className="px-6 py-5 border-b border-slate-soft flex justify-between items-start bg-neutral-soft/50">
          <div className="flex items-start gap-4 pr-6 min-w-0">
            {view ? <CompanyAvatar company={view.company} /> : <div className="w-11 h-11 rounded-lg bg-slate-soft/50 animate-pulse" />}
            <div className="min-w-0">
              <h2 id={titleId} className="text-xl font-serif font-medium text-slate-ink leading-tight">
                {view?.title ?? "Loading…"}
              </h2>
              {view && (
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-foreground-muted font-sans text-xs mt-1">
                  <span className="font-medium text-slate-ink">{view.company}</span>
                  <span aria-hidden="true">•</span>
                  <span>{view.location || (view.is_remote ? "Remote" : "Location unspecified")}</span>
                  {view.is_remote && view.location && (
                    <span className="px-1.5 py-0.5 rounded bg-amber-clay/10 text-amber-clay text-[11px] font-mono">
                      Remote
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>

          <button
            ref={closeRef}
            onClick={onClose}
            className="p-1.5 rounded hover:bg-slate-soft/50 transition-colors text-foreground-subtle hover:text-slate-ink shrink-0"
            aria-label="Close job details"
          >
            <X size={18} />
          </button>
        </div>

        {/* Content (Scrollable) */}
        {view && (
          <div className="flex-1 overflow-y-auto px-6 sm:px-8 py-6 space-y-6">
            <a
              href={view.apply_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex w-full items-center justify-center gap-2 py-2.5 px-4 bg-spruce-green hover:bg-spruce-green-hover text-warm-ivory font-sans font-medium text-sm rounded shadow-sm transition-colors"
            >
              Apply on company site <ExternalLink size={14} />
            </a>

            {/* Quick Metrics Cards */}
            <dl className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                { label: "Source", value: <span className="font-mono uppercase text-amber-clay">{view.source}</span> },
                {
                  label: "Posted",
                  value: view.posted_at
                    ? new Date(view.posted_at).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })
                    : "Unknown",
                },
                {
                  label: "Status",
                  value: (
                    <span className={view.is_active !== false ? "text-spruce-green" : "text-amber-clay"}>
                      {view.is_active !== false ? "Active" : "Closed"}
                    </span>
                  ),
                },
                {
                  label: "Compensation",
                  value: formatPay(view),
                },
              ].map(({ label, value }) => (
                <div key={label} className="border border-slate-soft rounded p-3 bg-neutral-soft/30">
                  <dt className="text-[11px] font-mono text-foreground-subtle uppercase tracking-wider mb-1">{label}</dt>
                  <dd className="text-xs font-sans font-medium text-slate-ink truncate">{value}</dd>
                </div>
              ))}
            </dl>

            {/* Core Skills Badges */}
            {view.skills && view.skills.length > 0 && (
              <section className="border-t border-slate-soft pt-4">
                <h3 className="text-xs font-mono uppercase tracking-wider text-foreground-subtle mb-2.5 flex items-center gap-1.5">
                  <Sparkles size={12} className="text-spruce-green" /> Extracted skills
                </h3>
                <ul className="flex flex-wrap gap-1.5">
                  {view.skills.map((skill) => (
                    <li
                      key={skill}
                      className="px-2.5 py-1 bg-spruce-green/10 text-spruce-green text-xs font-mono rounded border border-spruce-green/20 uppercase tracking-wider"
                    >
                      {skill}
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {/* Markdown Job Description (sanitized server-side; no raw HTML
                is rendered because rehype-raw is deliberately not used). */}
            <section className="border-t border-slate-soft pt-4">
              <h3 className="text-xs font-mono uppercase tracking-wider text-foreground-subtle mb-3">
                Job description
              </h3>

              {isLoadingDescription ? (
                <div className="space-y-2.5 animate-pulse" aria-label="Loading description">
                  {[100, 92, 96, 70, 88, 60].map((w, i) => (
                    <div key={i} className="h-3 rounded bg-slate-soft/60" style={{ width: `${w}%` }} />
                  ))}
                </div>
              ) : view.description ? (
                <div className="text-slate-ink font-sans text-sm">
                  <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                    {view.description}
                  </ReactMarkdown>
                </div>
              ) : (
                <div className="py-10 text-center border border-dashed border-slate-soft rounded p-8">
                  <p className="font-sans text-sm text-foreground-muted mb-3">
                    The full description isn&apos;t available here yet.
                  </p>
                  <a
                    href={view.apply_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 text-xs font-medium text-spruce-green hover:underline"
                  >
                    View the posting on the company site <ExternalLink size={12} />
                  </a>
                </div>
              )}
            </section>
          </div>
        )}
      </div>
    </div>
  );
}
