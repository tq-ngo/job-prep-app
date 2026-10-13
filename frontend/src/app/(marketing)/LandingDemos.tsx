"use client";

/**
 * Interactive islands for the landing page. Everything else on the page is
 * a server component; only these need client JS.
 */
import { useState, useEffect } from "react";
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
  const [isPaused, setIsPaused] = useState(false);
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
      <div className="absolute -inset-1.5 bg-gradient-to-r from-spruce-green/20 via-amber-clay/10 to-spruce-green/20 rounded-2xl blur-xl opacity-70" />
      
      <div className="relative bg-background border border-slate-soft rounded-xl shadow-2xl overflow-hidden">
        {/* Mock Window Title Bar */}
        <div className="px-5 py-3 border-b border-slate-soft bg-neutral-soft/50 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full bg-spruce-green animate-pulse" />
            <span className="font-mono text-[11px] font-semibold uppercase tracking-wider text-spruce-green">
              Live feed preview
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsPaused(!isPaused)}
              className="p-1 rounded text-foreground-subtle hover:text-slate-ink hover:bg-slate-soft/40 transition-colors"
              title={isPaused ? "Resume preview" : "Pause preview"}
              aria-label={isPaused ? "Resume preview" : "Pause preview"}
            >
              {isPaused ? <Play size={12} className="text-amber-clay" /> : <Pause size={12} />}
            </button>
            <span className="font-mono text-[11px] text-foreground-subtle px-1.5 py-0.5 rounded bg-slate-soft/40">
              Sample data
            </span>
          </div>
        </div>

        {/* Filter Toolbar */}
        <div className="px-4 py-2 border-b border-slate-soft flex items-center justify-between text-xs bg-background">
          <div className="flex gap-1">
            {(["All", "FAANG+", "Quant"] as const).map((cat) => (
              <button
                key={cat}
                onClick={() => setFilter(cat)}
                className={`px-2 py-0.5 rounded text-[11px] font-mono transition-colors ${
                  filter === cat
                    ? "bg-spruce-green/10 text-spruce-green font-medium"
                    : "text-foreground-subtle hover:text-slate-ink"
                }`}
              >
                {cat}
              </button>
            ))}
          </div>
          <span className="font-mono text-[11px] text-foreground-subtle">
            {filtered.length} visible
          </span>
        </div>

        {/* Feed List Items */}
        <div className="divide-y divide-slate-soft">
          {filtered.map((job) => (
            <div
              key={`${job.company}-${job.title}`}
              className="p-3.5 flex items-center justify-between hover:bg-neutral-soft/40 transition-colors group cursor-pointer"
            >
              <div className="min-w-0 flex-1 pr-3">
                <div className="flex items-center gap-2">
                  <p className="text-xs font-medium text-slate-ink truncate group-hover:text-spruce-green transition-colors">
                    {job.title}
                  </p>
                  <span className="text-[11px] font-mono px-1.5 py-0.2 rounded bg-spruce-green/10 text-spruce-green shrink-0">
                    {job.category}
                  </span>
                </div>
                <p className="text-[11px] text-foreground-muted mt-0.5">
                  {job.company} · {job.location}
                </p>
              </div>
              <div className="text-right shrink-0">
                <span className="font-mono text-[11px] uppercase tracking-wider text-amber-clay block">
                  {job.source}
                </span>
                <span className="font-mono text-[11px] text-foreground-subtle block mt-0.5">
                  {job.time}
                </span>
              </div>
            </div>
          ))}
        </div>

        {/* Card Footer */}
        <div className="px-4 py-2.5 bg-neutral-soft/30 border-t border-slate-soft flex items-center justify-between text-[11px] font-mono text-foreground-subtle">
          <span>Illustrative listings</span>
          <span className="text-spruce-green flex items-center gap-1">
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
    <div className="rounded-xl border border-slate-soft bg-background p-6 flex flex-col justify-between hover:border-spruce-green/30 transition-all">
      <div>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Cpu size={18} className="text-amber-clay" />
            <h3 className="font-serif text-base font-medium text-slate-ink">AI Intelligence Engine</h3>
          </div>
          <button
            onClick={() => setAnalyzed(!analyzed)}
            className="text-[11px] font-mono px-2 py-0.5 rounded border border-slate-soft hover:border-spruce-green text-foreground-muted hover:text-slate-ink transition-colors"
          >
            {analyzed ? "Reset" : "Transform with Gemini"}
          </button>
        </div>

        <p className="text-xs text-foreground-muted mb-4 leading-relaxed">
          Gemini distills raw market news into structured hiring signals and tech skill demand.
        </p>

        <div className="bg-neutral-soft border border-slate-soft rounded-lg p-3 text-xs space-y-2">
          <div className="font-mono text-[11px] text-foreground-subtle">Raw Headline:</div>
          <p className="italic text-foreground-muted">
            &quot;NVIDIA accelerates datacenter AI infrastructure investments with new Blackwell platform cluster deployments.&quot;
          </p>

          <div className="border-t border-slate-soft pt-2">
            {analyzed ? (
              <div className="space-y-1.5 text-xs animate-fadeSlideIn">
                <div className="font-mono text-[11px] text-spruce-green font-semibold flex items-center gap-1">
                  <Sparkles size={10} /> Example takeaways:
                </div>
                <div className="flex items-center gap-2 text-foreground-muted">
                  <span className="text-spruce-green">→</span> Hiring Sentiment: <strong className="text-spruce-green">Bullish (SWE/ML)</strong>
                </div>
                <div className="flex items-center gap-2 text-foreground-muted">
                  <span className="text-spruce-green">→</span> Impact: High infrastructure scale
                </div>
                <div className="flex flex-wrap gap-1 mt-1 pt-1">
                  {["CUDA", "Triton", "PyTorch", "RDMA"].map(skill => (
                    <span key={skill} className="px-1.5 py-0.5 bg-spruce-green/10 text-spruce-green font-mono text-[11px] rounded">
                      {skill}
                    </span>
                  ))}
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-between py-1 text-foreground-subtle font-mono text-[11px]">
                <span>Click &quot;Transform with Gemini&quot; to test AI parsing</span>
                <ArrowRight size={12} className="text-spruce-green" />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Interactive Bento Crawler Pipeline Card ──────────────────────────────
export function BentoPipelineCard() {
  return (
    <div className="rounded-xl border border-slate-soft bg-background p-6 hover:border-spruce-green/30 transition-all flex flex-col justify-between">
      <div>
        <div className="flex items-center gap-2 mb-3">
          <GitBranch size={18} className="text-spruce-green" />
          <h3 className="font-serif text-base font-medium text-slate-ink">Daily Crawler Pipeline</h3>
        </div>
        <p className="text-xs text-foreground-muted mb-4 leading-relaxed">
          Scrapers crawl 4 curated GitHub repos every 6 hours and LinkedIn daily, then fetch each posting&apos;s full description, sanitized and stripped of tracking pixels.
        </p>

        {/* Visual Pipeline Flow */}
        <div className="bg-neutral-soft border border-slate-soft rounded-lg p-3 space-y-2 font-mono text-[11px]">
          <div className="flex items-center justify-between text-foreground-subtle">
            <span className="flex items-center gap-1.5 text-slate-ink">
              <span className="w-1.5 h-1.5 rounded-full bg-spruce-green" /> GitHub Repos
            </span>
            <span className="text-amber-clay">every 6h</span>
          </div>
          <div className="flex items-center justify-between text-foreground-subtle">
            <span className="flex items-center gap-1.5 text-slate-ink">
              <span className="w-1.5 h-1.5 rounded-full bg-spruce-green" /> LinkedIn Guest API
            </span>
            <span className="text-amber-clay">daily</span>
          </div>
          
          {/* Deduplication Arrow */}
          <div className="border-t border-slate-soft pt-2 text-center text-foreground-subtle flex items-center justify-center gap-1 text-[11px] uppercase tracking-wider">
            <span>↓ 3-Tier Dedup: LRU → Redis → PostgreSQL ↓</span>
          </div>

          <div className="p-2 rounded bg-spruce-green/10 border border-spruce-green/20 text-spruce-green text-center font-medium">
            One canonical listing per role
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Interactive Bento Real-Time SSE Card ─────────────────────────────────
export function BentoSSECard({ initialCount }: { initialCount: number | null }) {
  const [count, setCount] = useState(initialCount ?? 0);
  const [animating, setAnimating] = useState(false);

  const triggerMockPing = () => {
    setAnimating(true);
    setCount(prev => prev + 1);
    setTimeout(() => setAnimating(false), 500);
  };

  return (
    <div className="rounded-xl border border-slate-soft bg-background p-6 hover:border-spruce-green/30 transition-all flex flex-col justify-between">
      <div>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Radio size={18} className="text-spruce-green" />
            <h3 className="font-serif text-base font-medium text-slate-ink">Real-Time Sync (SSE)</h3>
          </div>
          <span className="font-mono text-[11px] text-spruce-green bg-spruce-green/10 px-2 py-0.5 rounded">
            Live Stream
          </span>
        </div>
        <p className="text-xs text-foreground-muted mb-4 leading-relaxed">
          Server-Sent Events push new listings to your screen instantly. Redis Stream backlog preserves event state during re-connections.
        </p>

        <div className="bg-neutral-soft border border-slate-soft rounded-lg p-3 text-center">
          <p className="font-mono text-[11px] text-foreground-subtle uppercase tracking-wider mb-1">
            {initialCount === null ? "Demo counter" : "Roles added in the last 24h"}
          </p>
          <p className={`font-serif text-3xl font-medium text-slate-ink transition-transform ${animating ? "scale-110 text-spruce-green" : ""}`}>
            {count}
          </p>
          <button
            onClick={triggerMockPing}
            className="mt-3 w-full py-1.5 bg-background border border-slate-soft hover:border-spruce-green rounded font-mono text-[11px] text-slate-ink hover:text-spruce-green transition-colors cursor-pointer"
          >
            + Simulate a live event (demo)
          </button>
        </div>
      </div>
    </div>
  );
}
