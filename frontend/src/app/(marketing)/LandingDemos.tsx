"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { Pause, Play, Radio, ShieldCheck, SlidersHorizontal, Zap } from "lucide-react";
import Card from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { cn } from "@/components/ui/cn";

interface MockJob {
  id: string;
  title: string;
  company: string;
  location: string;
  category: "FAANG+" | "Quant" | "Startups";
  skills: string[];
  pay: string;
  sponsorship?: string;
  posted: string;
  summary: string;
}

const MOCK_JOBS: MockJob[] = [
  {
    id: "jane-street",
    title: "Quantitative Trading Intern",
    company: "Jane Street",
    location: "New York, NY",
    category: "Quant",
    skills: ["OCaml", "Python", "Probability"],
    pay: "$105/hr",
    posted: "2m ago",
    summary: "Work on pricing models, market microstructure research, and low-latency trading tools alongside desk engineers.",
  },
  {
    id: "stripe",
    title: "Software Engineering Intern",
    company: "Stripe",
    location: "San Francisco, CA",
    category: "FAANG+",
    skills: ["Ruby", "TypeScript", "Distributed Systems"],
    pay: "$62/hr",
    sponsorship: "Sponsorship available",
    posted: "9m ago",
    summary: "Ship API improvements across payment routing, idempotency primitives, and merchant developer tooling.",
  },
  {
    id: "citadel",
    title: "Systems Engineering Intern",
    company: "Citadel Securities",
    location: "Chicago, IL",
    category: "Quant",
    skills: ["C++", "Linux", "Networking"],
    pay: "$110/hr",
    posted: "18m ago",
    summary: "Profile kernel bypass paths, lock-free queues, and real-time market data feeds.",
  },
  {
    id: "linear",
    title: "Product Engineering Intern",
    company: "Linear",
    location: "Remote",
    category: "Startups",
    skills: ["TypeScript", "React", "GraphQL"],
    pay: "$58/hr",
    sponsorship: "Sponsorship available",
    posted: "27m ago",
    summary: "Build fast local-first sync features, keyboard workflows, and issue-tracking views.",
  },
  {
    id: "anthropic",
    title: "Infrastructure Engineering Intern",
    company: "Anthropic",
    location: "San Francisco, CA",
    category: "FAANG+",
    skills: ["Python", "Kubernetes", "Rust"],
    pay: "$75/hr",
    posted: "41m ago",
    summary: "Improve cluster scheduling, inference latency telemetry, and evaluation pipelines.",
  },
  {
    id: "vercel",
    title: "Frontend Platform Intern",
    company: "Vercel",
    location: "Remote",
    category: "Startups",
    skills: ["Next.js", "TypeScript", "Rust"],
    pay: "$60/hr",
    posted: "54m ago",
    summary: "Work on build caching, bundler diagnostics, and developer dashboard ergonomics.",
  },
];

const CATEGORIES = ["All", "FAANG+", "Quant", "Startups"] as const;
const VISIBLE_ROWS = 4;

const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

function subscribeReducedMotion(callback: () => void) {
  const mq = window.matchMedia?.(REDUCED_MOTION_QUERY);
  if (!mq) return () => {};
  mq.addEventListener("change", callback);
  return () => mq.removeEventListener("change", callback);
}

function getReducedMotionSnapshot(): boolean {
  return Boolean(window.matchMedia?.(REDUCED_MOTION_QUERY).matches);
}

function getReducedMotionServerSnapshot(): boolean {
  return false;
}

function usePrefersReducedMotion(): boolean {
  return useSyncExternalStore(
    subscribeReducedMotion,
    getReducedMotionSnapshot,
    getReducedMotionServerSnapshot,
  );
}

export function InteractiveLiveCard() {
  const reducedMotion = usePrefersReducedMotion();
  const [category, setCategory] = useState<(typeof CATEGORIES)[number]>("All");
  const [paused, setPaused] = useState(false);
  const [userToggled, setUserToggled] = useState(false);
  const [headIndex, setHeadIndex] = useState(0);
  const [selectedId, setSelectedId] = useState<string>(MOCK_JOBS[0].id);

  const effectivelyPaused = userToggled ? paused : reducedMotion;

  useEffect(() => {
    if (effectivelyPaused || category !== "All") return;
    const timer = window.setInterval(() => {
      setHeadIndex((prev) => (prev + 1) % MOCK_JOBS.length);
    }, 3000);
    return () => window.clearInterval(timer);
  }, [effectivelyPaused, category]);

  const orderedJobs =
    category === "All"
      ? Array.from({ length: VISIBLE_ROWS }, (_, offset) => MOCK_JOBS[(headIndex + offset) % MOCK_JOBS.length])
      : MOCK_JOBS.filter((j) => j.category === category);

  const selectedJob = orderedJobs.find((j) => j.id === selectedId) ?? orderedJobs[0];

  const togglePause = () => {
    setUserToggled(true);
    setPaused(!effectivelyPaused);
  };

  return (
    <div className="rounded-xl border border-outline-variant bg-surface-container-lowest shadow-level-1 dark:shadow-none overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 border-b border-outline-variant bg-surface-container-low">
        <div className="flex items-center gap-2">
          <span aria-hidden="true" className="w-2 h-2 rounded-full bg-primary" />
          <span className="text-label-medium font-medium text-on-surface">Board preview</span>
          <span className="text-label-small text-on-surface-variant">Sample listings</span>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div role="group" aria-label="Filter sample roles" className="flex items-center gap-1">
            {CATEGORIES.map((cat) => {
              const active = category === cat;
              return (
                <button
                  key={cat}
                  type="button"
                  aria-pressed={active}
                  onClick={() => {
                    setCategory(cat);
                    setHeadIndex(0);
                  }}
                  className={cn(
                    "px-3 py-1 min-h-7 rounded-full text-label-small font-medium transition-colors cursor-pointer",
                    active
                      ? "bg-primary text-on-primary"
                      : "bg-surface text-on-surface-variant border border-outline-variant hover:text-on-surface hover:bg-on-surface/8",
                  )}
                >
                  {cat}
                </button>
              );
            })}
          </div>

          <button
            type="button"
            onClick={togglePause}
            aria-label={effectivelyPaused ? "Resume preview" : "Pause preview"}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 min-h-7 rounded-full border border-outline-variant bg-surface text-label-small font-medium text-on-surface-variant hover:text-on-surface hover:bg-on-surface/8 transition-colors cursor-pointer"
          >
            {effectivelyPaused ? (
              <Play size={14} strokeWidth={1.5} aria-hidden="true" />
            ) : (
              <Pause size={14} strokeWidth={1.5} aria-hidden="true" />
            )}
            <span>{effectivelyPaused ? "Resume" : "Pause"}</span>
          </button>
        </div>
      </div>

      <p role="status" className="sr-only">
        {orderedJobs.length} sample roles visible for {category}.
      </p>

      <div className="grid lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)] divide-y lg:divide-y-0 lg:divide-x divide-outline-variant">
        <div className="divide-y divide-outline-variant">
          {orderedJobs.map((job) => {
            const isSelected = job.id === selectedJob.id;
            return (
              <button
                key={job.id}
                type="button"
                onClick={() => setSelectedId(job.id)}
                aria-current={isSelected ? "true" : undefined}
                className={cn(
                  "w-full text-left px-4 py-3.5 border-l-4 transition-colors cursor-pointer block",
                  isSelected
                    ? "border-l-primary bg-primary-container/35"
                    : "border-l-transparent hover:bg-surface-container-low",
                )}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-title-small font-semibold text-on-surface truncate">{job.title}</p>
                    <p className="text-body-small text-on-surface-variant mt-0.5 truncate">
                      {job.company} · {job.location}
                    </p>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="font-mono text-label-medium font-medium text-on-surface tabular-nums">{job.pay}</p>
                    <p className="font-mono text-label-small text-on-surface-variant tabular-nums">{job.posted}</p>
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-1.5 mt-2.5">
                  {job.skills.map((skill) => (
                    <span
                      key={skill}
                      className="px-2 py-0.5 rounded-xs bg-surface-container-low border border-outline-variant font-mono text-2xs text-on-surface-variant"
                    >
                      {skill}
                    </span>
                  ))}
                  {job.sponsorship && (
                    <span className="px-2 py-0.5 rounded-xs bg-secondary-container text-on-secondary-container font-mono text-2xs font-medium">
                      {job.sponsorship}
                    </span>
                  )}
                </div>
              </button>
            );
          })}
        </div>

        <div className="p-6 flex flex-col justify-between gap-6 bg-surface">
          <div>
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-label-medium font-medium text-primary">{selectedJob.company}</p>
                <h3 className="text-title-large font-semibold text-on-surface mt-1">{selectedJob.title}</h3>
                <p className="text-body-small text-on-surface-variant mt-1">
                  {selectedJob.location} · <span className="font-mono tabular-nums">{selectedJob.pay}</span>
                </p>
              </div>
              <span className="px-2.5 py-1 rounded-xs bg-surface-container-low border border-outline-variant font-mono text-label-small text-on-surface-variant shrink-0">
                {selectedJob.category}
              </span>
            </div>

            <p className="text-body-medium text-on-surface-variant mt-4 leading-relaxed">{selectedJob.summary}</p>

            <div className="mt-5">
              <p className="text-label-medium font-medium text-on-surface-variant mb-2">Extracted skills</p>
              <div className="flex flex-wrap gap-1.5">
                {selectedJob.skills.map((skill) => (
                  <span
                    key={skill}
                    className="px-2.5 py-1 rounded-xs bg-surface-container-low border border-outline-variant font-mono text-label-small text-on-surface"
                  >
                    {skill}
                  </span>
                ))}
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between gap-4 pt-4 border-t border-outline-variant text-label-small text-on-surface-variant">
            <span>Deduplicated across GitHub and LinkedIn</span>
            <span className="font-mono tabular-nums">Updated {selectedJob.posted}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export function BentoSSECard({ initialCount }: { initialCount: number | null }) {
  const [simulated, setSimulated] = useState(0);
  const [recentPulse, setRecentPulse] = useState(false);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    };
  }, []);

  const simulateEvent = () => {
    setSimulated((n) => n + 1);
    setRecentPulse(true);
    if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(() => {
      setRecentPulse(false);
      timerRef.current = null;
    }, 600);
  };

  return (
    <Card variant="outlined" className="p-6 flex flex-col justify-between gap-6">
      <div>
        <div className="flex items-center gap-2 text-on-surface-variant mb-3">
          <Radio size={16} strokeWidth={1.5} aria-hidden="true" />
          <span className="text-label-medium font-medium">Live stream</span>
        </div>
        <h3 className="text-title-large font-semibold text-on-surface">New listings push directly to open tabs</h3>
        <p className="text-body-medium text-on-surface-variant mt-2">
          Background crawlers stream newly discovered roles and extracted skills over Server-Sent Events with no manual reload.
        </p>
      </div>

      <div className="rounded-lg bg-surface-container-low p-4 space-y-4">
        <div className="grid grid-cols-2 gap-4">
          {initialCount !== null && (
            <div>
              <p className="text-label-small text-on-surface-variant">Added in last 24h</p>
              <p className="font-mono text-headline-small font-semibold text-on-surface tabular-nums mt-1">
                {initialCount.toLocaleString("en-US")}
              </p>
            </div>
          )}
          <div>
            <p className="text-label-small text-on-surface-variant">Simulated events</p>
            <p
              className={cn(
                "font-mono text-headline-small font-semibold tabular-nums mt-1 transition-colors",
                recentPulse ? "text-primary" : "text-on-surface",
              )}
            >
              {simulated}
            </p>
          </div>
        </div>

        <Button variant="outlined" size="sm" onClick={simulateEvent} className="w-full">
          Simulate a live event
        </Button>
      </div>
    </Card>
  );
}

export function PipelineHighlights({ newLast24h }: { newLast24h: number | null }) {
  return (
    <div className="grid lg:grid-cols-12 gap-6">
      <div className="lg:col-span-7 grid sm:grid-cols-2 gap-6">
        <Card variant="outlined" className="p-6 flex flex-col justify-between gap-4 sm:col-span-2">
          <div>
            <div className="flex items-center gap-2 text-on-surface-variant mb-3">
              <Zap size={16} strokeWidth={1.5} aria-hidden="true" />
              <span className="text-label-medium font-medium">Hourly ingestion</span>
            </div>
            <h3 className="text-title-large font-semibold text-on-surface">GitHub and LinkedIn merged into one canonical row</h3>
            <p className="text-body-medium text-on-surface-variant mt-2 max-w-2xl">
              Cross-posted internships are linked before descriptions are fetched, so each role appears once with its freshest apply link, location, and pay range.
            </p>
          </div>
          <div className="grid grid-cols-3 gap-3 pt-4 border-t border-outline-variant text-label-small">
            <div>
              <p className="font-mono font-semibold text-on-surface">Hourly</p>
              <p className="text-on-surface-variant mt-0.5">Crawl cadence</p>
            </div>
            <div>
              <p className="font-mono font-semibold text-on-surface">3-layer</p>
              <p className="text-on-surface-variant mt-0.5">Canonical dedup</p>
            </div>
            <div>
              <p className="font-mono font-semibold text-on-surface">Structured</p>
              <p className="text-on-surface-variant mt-0.5">Skills &amp; visa tags</p>
            </div>
          </div>
        </Card>

        <Card variant="outlined" className="p-6 flex flex-col gap-3">
          <div className="flex items-center gap-2 text-on-surface-variant">
            <SlidersHorizontal size={16} strokeWidth={1.5} aria-hidden="true" />
            <span className="text-label-medium font-medium">Fast filtering</span>
          </div>
          <h3 className="text-title-medium font-semibold text-on-surface">Filter by category, skill, and work type</h3>
          <p className="text-body-medium text-on-surface-variant">
            Slice the board by FAANG+, Quant, remote availability, and extracted skills with shareable URL parameters.
          </p>
        </Card>

        <Card variant="outlined" className="p-6 flex flex-col gap-3">
          <div className="flex items-center gap-2 text-on-surface-variant">
            <ShieldCheck size={16} strokeWidth={1.5} aria-hidden="true" />
            <span className="text-label-medium font-medium">Clean descriptions</span>
          </div>
          <h3 className="text-title-medium font-semibold text-on-surface">Sanitized job details without tracker clutter</h3>
          <p className="text-body-medium text-on-surface-variant">
            Scraped descriptions are stripped to clean Markdown on ingest so you can read requirements side by side before clicking apply.
          </p>
        </Card>
      </div>

      <div className="lg:col-span-5 flex flex-col">
        <div className="flex-1 flex flex-col [&>*]:flex-1">
          <BentoSSECard initialCount={newLast24h} />
        </div>
      </div>
    </div>
  );
}
