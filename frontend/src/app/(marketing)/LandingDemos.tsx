"use client";

/**
 * Interactive islands for the landing page. Everything else on the page is
 * a server component; only these need client JS.
 */
import { useState, useEffect, useRef } from "react";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import {
  Sparkles,
  ArrowRight,
  Cpu,
  Radio,
  Play,
  Pause,
  CheckCircle2,
  GitBranch,
} from "lucide-react";
import Badge from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import Card from "@/components/ui/Card";

// ── Interactive Job Preview Data ─────────────────────────────────────────
interface MockJob {
  title: string;
  company: string;
  location: string;
  source: "github" | "linkedin";
  category: "FAANG+" | "Quant" | "Others";
  time: string;
}

const MOCK_JOBS: MockJob[] = [
  { title: "Software Engineer Intern", company: "Google", location: "Mountain View, CA", source: "github", category: "FAANG+", time: "2m ago" },
  { title: "Quantitative Trading Intern", company: "Jane Street", location: "New York, NY", source: "github", category: "Quant", time: "5m ago" },
  { title: "Frontend Engineer Intern", company: "Meta", location: "Menlo Park, CA", source: "linkedin", category: "FAANG+", time: "11m ago" },
  { title: "Quantitative Dev Intern", company: "Citadel", location: "New York, NY", source: "github", category: "Quant", time: "18m ago" },
  { title: "Full Stack Engineer Intern", company: "Stripe", location: "San Francisco, CA", source: "linkedin", category: "Others", time: "24m ago" },
  { title: "Distributed Systems Intern", company: "Netflix", location: "Los Gatos, CA", source: "github", category: "FAANG+", time: "30m ago" },
  { title: "Core Engineering Intern", company: "Two Sigma", location: "New York, NY", source: "github", category: "Quant", time: "42m ago" },
  { title: "Cloud Systems Intern", company: "Amazon", location: "Seattle, WA", source: "linkedin", category: "FAANG+", time: "55m ago" },
];

export function InteractiveLiveCard() {
  const [filter, setFilter] = useState<"All" | "FAANG+" | "Quant">("All");
  // Auto-rotation is motion: off by default for people who ask the OS for
  // less (WCAG 2.2.2), though they can still start it. Their own choice wins.
  const reduceMotion = useMediaQuery("(prefers-reduced-motion: reduce)");
  const [pausedByUser, setPausedByUser] = useState<boolean | null>(null);
  const isPaused = pausedByUser ?? reduceMotion;
  const [displayedJobs, setDisplayedJobs] = useState<MockJob[]>(MOCK_JOBS.slice(0, 4));

  useEffect(() => {
    if (isPaused) return;
    const interval = setInterval(() => {
      setDisplayedJobs((prev) => {
        const nextIdx = (MOCK_JOBS.indexOf(prev[0]) + 1) % MOCK_JOBS.length;
        const nextItem = MOCK_JOBS[nextIdx];
        const updated = [nextItem, ...prev.slice(0, 3)];
        return updated;
      });
    }, 2800);
    return () => clearInterval(interval);
  }, [isPaused]);

  const filtered = filter === "All" 
    ? displayedJobs 
    : displayedJobs.filter(j => j.category === filter);

  return (
    <div className="relative w-full max-w-lg mx-auto lg:mx-0">
      {/* Glow highlight */}
      <div className="absolute -inset-1.5 bg-gradient-to-r from-primary/20 via-secondary-container/40 to-primary/20 rounded-xl blur-xl opacity-70" />

      <div className="relative bg-surface-container-lowest dark:bg-surface-container-default border border-outline-variant rounded-lg shadow-level-3 overflow-hidden">
        {/* Mock Window Title Bar */}
        <div className="px-5 py-3 border-b border-outline-variant bg-surface-container-low flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full bg-primary animate-pulse motion-reduce:animate-none" />
            <span className="font-mono text-label-small font-semibold uppercase tracking-wider text-primary">
              Live feed preview
            </span>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="text"
              size="xs"
              onClick={() => setPausedByUser(!isPaused)}
              title={isPaused ? "Resume preview" : "Pause preview"}
              aria-label={isPaused ? "Resume preview" : "Pause preview"}
            >
              {isPaused ? <Play size={12} aria-hidden="true" className="text-primary" /> : <Pause size={12} aria-hidden="true" />}
            </Button>
            <span className="font-mono text-label-small text-on-surface-variant px-2 py-0.5 rounded-full bg-surface-container-default">
              Sample data
            </span>
          </div>
        </div>

        {/* Filter Toolbar */}
        <div className="px-4 py-2 border-b border-outline-variant flex items-center justify-between text-body-small bg-surface">
          <div className="flex gap-1">
            {(["All", "FAANG+", "Quant"] as const).map((cat) => (
              <button
                key={cat}
                type="button"
                aria-pressed={filter === cat}
                onClick={() => setFilter(cat)}
                className={`px-2.5 py-0.5 rounded-full text-label-small font-mono transition-colors ${
                  filter === cat
                    ? "bg-secondary-container text-on-secondary-container font-semibold"
                    : "text-on-surface-variant hover:text-on-surface hover:bg-on-surface/8 focus-visible:bg-on-surface/12"
                }`}
              >
                {cat}
              </button>
            ))}
          </div>
          <span className="font-mono text-label-small text-on-surface-variant">
            <span role="status">{filtered.length} visible</span>
          </span>
        </div>

        {/* Feed List Items */}
        {/* Not a live region: announcing a new row every 2.8s would talk over
            everything else. The visible count above is announced on filter. */}
        <div className="divide-y divide-outline-variant" aria-label="Sample job feed, updating automatically" role="group">
          {filtered.map((job) => (
            <div
              key={`${job.company}-${job.title}`}
              className="p-3.5 flex items-center justify-between hover:bg-on-surface/8 transition-colors group cursor-pointer"
            >
              <div className="min-w-0 flex-1 pr-3">
                <div className="flex items-center gap-2">
                  <p className="text-label-large font-medium text-on-surface truncate group-hover:text-primary transition-colors">
                    {job.title}
                  </p>
                  <Badge variant="skill">{job.category}</Badge>
                </div>
                <p className="text-label-small text-on-surface-variant mt-0.5">
                  {job.company} · {job.location}
                </p>
              </div>
              <div className="text-right shrink-0">
                <span className="font-mono text-label-small uppercase tracking-wider text-primary block">
                  {job.source}
                </span>
                <span className="font-mono text-label-small text-on-surface-variant block mt-0.5">
                  {job.time}
                </span>
              </div>
            </div>
          ))}
        </div>

        {/* Card Footer */}
        <div className="px-4 py-2.5 bg-surface-container-low border-t border-outline-variant flex items-center justify-between text-label-small font-mono text-on-surface-variant">
          <span>Illustrative listings</span>
          <span className="text-primary flex items-center gap-1">
            <CheckCircle2 size={11} /> Pushed over SSE in the app
          </span>
        </div>
      </div>
    </div>
  );
}

// ── Interactive Bento AI Demo Card ───────────────────────────────────────
export function BentoAIDemoCard() {
  const [analyzed, setAnalyzed] = useState(false);

  return (
    <Card tone="elevated" interactive className="flex flex-col justify-between">
      <div>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Cpu size={18} className="text-primary" />
            <h3 className="font-serif text-title-medium font-medium text-on-surface">AI Intelligence Engine</h3>
          </div>
          <Button variant="tonal" size="xs" onClick={() => setAnalyzed(!analyzed)}>
            {analyzed ? "Reset" : "Transform with Gemini"}
          </Button>
        </div>

        <p className="text-body-small text-on-surface-variant mb-4 leading-relaxed">
          Gemini distills raw market news into structured hiring signals and tech skill demand.
        </p>

        <div className="bg-surface-container-low border border-outline-variant rounded-md p-3 text-body-small space-y-2">
          <div className="font-mono text-label-small text-on-surface-variant">Raw Headline:</div>
          <p className="italic text-on-surface-variant">
            &quot;NVIDIA accelerates datacenter AI infrastructure investments with new Blackwell platform cluster deployments.&quot;
          </p>

          <div className="border-t border-outline-variant pt-2">
            {analyzed ? (
              <div className="space-y-1.5 text-body-small animate-fadeSlideIn motion-reduce:animate-none">
                <div className="font-mono text-label-small text-primary font-semibold flex items-center gap-1">
                  <Sparkles size={10} /> Example takeaways:
                </div>
                <div className="flex items-center gap-2 text-on-surface-variant">
                  <span className="text-primary">→</span> Hiring Sentiment: <strong className="text-primary">Bullish (SWE/ML)</strong>
                </div>
                <div className="flex items-center gap-2 text-on-surface-variant">
                  <span className="text-primary">→</span> Impact: High infrastructure scale
                </div>
                <div className="flex flex-wrap gap-1 mt-1 pt-1">
                  {["CUDA", "Triton", "PyTorch", "RDMA"].map((skill) => (
                    <Badge key={skill} variant="skill">
                      {skill}
                    </Badge>
                  ))}
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-between py-1 text-on-surface-variant font-mono text-label-small">
                <span>Click &quot;Transform with Gemini&quot; to test AI parsing</span>
                <ArrowRight size={12} className="text-primary" />
              </div>
            )}
          </div>
        </div>
      </div>
    </Card>
  );
}


// ── Interactive Bento Real-Time SSE Card ─────────────────────────────────
export function BentoSSECard({ initialCount }: { initialCount: number | null }) {
  // The simulation counts separately: it used to add to the real "last 24h"
  // figure, so the page's one live statistic could be inflated by clicking.
  const [simulated, setSimulated] = useState(0);
  const [animating, setAnimating] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  useEffect(() => () => clearTimeout(timer.current), []);

  const triggerMockPing = () => {
    setAnimating(true);
    setSimulated((n) => n + 1);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setAnimating(false), 500);
  };

  return (
    <Card tone="elevated" interactive className="flex flex-col justify-between">
      <div>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Radio size={18} aria-hidden="true" className="text-primary" />
            <h3 className="font-serif text-title-medium font-medium text-on-surface">Real-Time Sync (SSE)</h3>
          </div>
          <Badge variant="skill">Live Stream</Badge>
        </div>
        <p className="text-body-small text-on-surface-variant mb-4 leading-relaxed">
          Server-Sent Events push new listings to your screen instantly. Redis Stream backlog preserves event state during re-connections.
        </p>

        <div className="bg-surface-container-low border border-outline-variant rounded-md p-3 text-center">
          {initialCount !== null && (
            <p className="font-mono text-label-small text-on-surface-variant uppercase tracking-wider mb-3">
              <span className="font-serif text-title-medium normal-case tracking-normal text-on-surface">{initialCount.toLocaleString("en-US")}</span>{" "}
              roles added in the last 24h
            </p>
          )}
          <p className="font-mono text-label-small text-on-surface-variant uppercase tracking-wider mb-1">Simulated events</p>
          <p
            aria-live="polite"
            className={`font-serif text-headline-medium font-medium transition-transform motion-reduce:transition-none ${animating ? "scale-110 motion-reduce:scale-100 text-primary" : "text-on-surface"}`}
          >
            {simulated}
          </p>
          <Button variant="outlined" size="sm" block onClick={triggerMockPing} className="mt-3">
            + Simulate a live event (demo)
          </Button>
        </div>
      </div>
    </Card>
  );
}

// ── Daily Crawler Pipeline Card ──────────────────────────────────────────
export function BentoPipelineCard() {
  return (
    <Card tone="elevated" interactive className="flex flex-col justify-between">
      <div>
        <div className="flex items-center gap-2 mb-3">
          <GitBranch size={18} aria-hidden="true" className="text-primary" />
          <h3 className="font-serif text-title-medium font-medium text-on-surface">Daily Crawler Pipeline</h3>
        </div>
        <p className="text-body-small text-on-surface-variant mb-4 leading-relaxed">
          Scrapers crawl 4 curated GitHub repos every 6 hours and LinkedIn daily, then fetch each posting&apos;s full description, sanitized and stripped of tracking pixels.
        </p>

        {/* Visual Pipeline Flow */}
        <div className="bg-surface-container-low border border-outline-variant rounded-md p-3 space-y-2 font-mono text-label-small">
          <div className="flex items-center justify-between text-on-surface-variant">
            <span className="flex items-center gap-1.5 text-on-surface">
              <span className="w-1.5 h-1.5 rounded-full bg-primary" /> GitHub Repos
            </span>
            <span className="text-primary">every 6h</span>
          </div>
          <div className="flex items-center justify-between text-on-surface-variant">
            <span className="flex items-center gap-1.5 text-on-surface">
              <span className="w-1.5 h-1.5 rounded-full bg-primary" /> LinkedIn Guest API
            </span>
            <span className="text-primary">daily</span>
          </div>

          {/* Deduplication Arrow */}
          <div className="border-t border-outline-variant pt-2 text-center text-on-surface-variant flex items-center justify-center gap-1 text-label-small uppercase tracking-wider">
            <span>↓ 3-Tier Dedup: LRU → Redis → PostgreSQL ↓</span>
          </div>

          <div className="p-2 rounded-sm bg-primary-container border border-primary/20 text-on-primary-container text-center font-medium">
            One canonical listing per role
          </div>
        </div>
      </div>
    </Card>
  );
}
