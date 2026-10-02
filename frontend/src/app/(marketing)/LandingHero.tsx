"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { 
  Sparkles, 
  ArrowRight, 
  RefreshCw, 
  Layers, 
  Activity, 
  Cpu, 
  Search, 
  ShieldCheck, 
  Radio, 
  ExternalLink,
  Play,
  Pause,
  CheckCircle2,
  Database,
  GitBranch
} from "lucide-react";
import ThemeToggle from "@/components/ThemeToggle";
import { authApi } from "@/lib/api";

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

function InteractiveLiveCard() {
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
              Live Feed Stream (SSE)
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsPaused(!isPaused)}
              className="p-1 rounded text-foreground-subtle hover:text-slate-ink hover:bg-slate-soft/40 transition-colors"
              title={isPaused ? "Resume live feed" : "Pause live feed"}
            >
              {isPaused ? <Play size={12} className="text-amber-clay" /> : <Pause size={12} />}
            </button>
            <span className="font-mono text-[10px] text-foreground-subtle px-1.5 py-0.5 rounded bg-slate-soft/40">
              Active
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
          <span className="font-mono text-[10px] text-foreground-subtle">
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
                  <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-spruce-green/10 text-spruce-green shrink-0">
                    {job.category}
                  </span>
                </div>
                <p className="text-[11px] text-foreground-muted mt-0.5">
                  {job.company} · {job.location}
                </p>
              </div>
              <div className="text-right shrink-0">
                <span className="font-mono text-[10px] uppercase tracking-wider text-amber-clay block">
                  {job.source}
                </span>
                <span className="font-mono text-[9px] text-foreground-subtle block mt-0.5">
                  {job.time}
                </span>
              </div>
            </div>
          ))}
        </div>

        {/* Card Footer */}
        <div className="px-4 py-2.5 bg-neutral-soft/30 border-t border-slate-soft flex items-center justify-between text-[11px] font-mono text-foreground-subtle">
          <span>Latency: ~180ms</span>
          <span className="text-spruce-green flex items-center gap-1">
            <CheckCircle2 size={11} /> 100% Ingestion Integrity
          </span>
        </div>
      </div>
    </div>
  );
}

// ── Interactive Bento AI Demo Card ───────────────────────────────────────
function BentoAIDemoCard() {
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
            className="text-[10px] font-mono px-2 py-0.5 rounded border border-slate-soft hover:border-spruce-green text-foreground-muted hover:text-slate-ink transition-colors"
          >
            {analyzed ? "Reset" : "Transform with Gemini"}
          </button>
        </div>

        <p className="text-xs text-foreground-muted mb-4 leading-relaxed">
          Gemini 3.8 Flash distills raw market news into structured hiring signals and tech skill demand.
        </p>

        <div className="bg-neutral-soft border border-slate-soft rounded-lg p-3 text-xs space-y-2">
          <div className="font-mono text-[10px] text-foreground-subtle">Raw Headline:</div>
          <p className="italic text-foreground-muted">
            &quot;NVIDIA accelerates datacenter AI infrastructure investments with new Blackwell platform cluster deployments.&quot;
          </p>

          <div className="border-t border-slate-soft pt-2">
            {analyzed ? (
              <div className="space-y-1.5 text-xs animate-fadeSlideIn">
                <div className="font-mono text-[10px] text-spruce-green font-semibold flex items-center gap-1">
                  <Sparkles size={10} /> Gemini 3.8 Takeaways:
                </div>
                <div className="flex items-center gap-2 text-foreground-muted">
                  <span className="text-spruce-green">→</span> Hiring Sentiment: <strong className="text-spruce-green">Bullish (SWE/ML)</strong>
                </div>
                <div className="flex items-center gap-2 text-foreground-muted">
                  <span className="text-spruce-green">→</span> Impact: High infrastructure scale
                </div>
                <div className="flex flex-wrap gap-1 mt-1 pt-1">
                  {["CUDA", "Triton", "PyTorch", "RDMA"].map(skill => (
                    <span key={skill} className="px-1.5 py-0.5 bg-spruce-green/10 text-spruce-green font-mono text-[9px] rounded">
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
function BentoPipelineCard() {
  return (
    <div className="rounded-xl border border-slate-soft bg-background p-6 hover:border-spruce-green/30 transition-all flex flex-col justify-between">
      <div>
        <div className="flex items-center gap-2 mb-3">
          <GitBranch size={18} className="text-spruce-green" />
          <h3 className="font-serif text-base font-medium text-slate-ink">Daily Crawler Pipeline</h3>
        </div>
        <p className="text-xs text-foreground-muted mb-4 leading-relaxed">
          Automated scrapers crawl 4 curated GitHub repos and LinkedIn guest APIs, pulling full job descriptions with zero HTML tracking beacons.
        </p>

        {/* Visual Pipeline Flow */}
        <div className="bg-neutral-soft border border-slate-soft rounded-lg p-3 space-y-2 font-mono text-[10px]">
          <div className="flex items-center justify-between text-foreground-subtle">
            <span className="flex items-center gap-1.5 text-slate-ink">
              <span className="w-1.5 h-1.5 rounded-full bg-spruce-green" /> GitHub Repos
            </span>
            <span className="text-amber-clay">~125 reqs</span>
          </div>
          <div className="flex items-center justify-between text-foreground-subtle">
            <span className="flex items-center gap-1.5 text-slate-ink">
              <span className="w-1.5 h-1.5 rounded-full bg-spruce-green" /> LinkedIn Guest API
            </span>
            <span className="text-amber-clay">5 pages · 25/pg</span>
          </div>
          
          {/* Deduplication Arrow */}
          <div className="border-t border-slate-soft pt-2 text-center text-foreground-subtle flex items-center justify-center gap-1 text-[9px] uppercase tracking-wider">
            <span>↓ 3-Tier Dedup: LRU → Redis → PostgreSQL ↓</span>
          </div>

          <div className="p-2 rounded bg-spruce-green/10 border border-spruce-green/20 text-spruce-green text-center font-medium">
            Single Canonical Listing · Zero Duplicates
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Interactive Bento Real-Time SSE Card ─────────────────────────────────
function BentoSSECard() {
  const [count, setCount] = useState(128);
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
          <span className="font-mono text-[10px] text-spruce-green bg-spruce-green/10 px-2 py-0.5 rounded">
            Live Stream
          </span>
        </div>
        <p className="text-xs text-foreground-muted mb-4 leading-relaxed">
          Server-Sent Events push new listings to your screen instantly. Redis Stream backlog preserves event state during re-connections.
        </p>

        <div className="bg-neutral-soft border border-slate-soft rounded-lg p-3 text-center">
          <p className="font-mono text-[10px] text-foreground-subtle uppercase tracking-wider mb-1">
            Jobs Ingested Today
          </p>
          <p className={`font-serif text-3xl font-medium text-slate-ink transition-transform ${animating ? "scale-110 text-spruce-green" : ""}`}>
            {count}
          </p>
          <button
            onClick={triggerMockPing}
            className="mt-3 w-full py-1.5 bg-background border border-slate-soft hover:border-spruce-green rounded font-mono text-[10px] text-slate-ink hover:text-spruce-green transition-colors cursor-pointer"
          >
            + Simulate Live Event Push
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main Landing Hero Component ──────────────────────────────────────────
export default function LandingHero() {
  return (
    <div className="min-h-screen bg-background text-foreground font-sans selection:bg-spruce-green/20 selection:text-spruce-green">

      {/* Global Persistent Header */}
      <header className="fixed top-0 inset-x-0 z-50 backdrop-blur-md bg-background/85 border-b border-slate-soft">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link 
            href="/" 
            className="font-serif text-xl font-medium tracking-tight text-slate-ink hover:text-spruce-green transition-colors"
          >
            JobPrep
          </Link>

          <nav className="hidden md:flex items-center gap-6 text-xs font-medium text-foreground-muted">
            <a href="#features" className="hover:text-slate-ink transition-colors">Features</a>
            <a href="#demo" className="hover:text-slate-ink transition-colors">AI Intelligence</a>
            <Link href="/news" className="hover:text-slate-ink transition-colors">Tech Radar</Link>
            <Link href="/jobs" className="hover:text-slate-ink transition-colors">Job Board</Link>
          </nav>

          <div className="flex items-center gap-3">
            <ThemeToggle />
            <Link 
              href="/login" 
              className="text-xs font-medium text-foreground-muted hover:text-slate-ink transition-colors px-2 py-1"
            >
              Sign In
            </Link>
            <Link
              href="/register"
              className="text-xs font-medium bg-spruce-green hover:bg-spruce-green-hover text-warm-ivory px-3.5 py-2 rounded shadow-xs transition-colors"
            >
              Get Started
            </Link>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="pt-32 pb-16 lg:pt-40 lg:pb-24">
        <div className="max-w-6xl mx-auto px-6">
          <div className="grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
            
            {/* Left: Editorial Copy */}
            <div>
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-spruce-green/10 border border-spruce-green/20 mb-6">
                <div className="w-1.5 h-1.5 rounded-full bg-spruce-green animate-pulse" />
                <span className="font-mono text-[10px] uppercase tracking-widest text-spruce-green font-semibold">
                  Crawling ~125+ SWE intern roles daily
                </span>
              </div>

              <h1 className="text-4xl sm:text-5xl lg:text-6xl font-serif font-medium text-slate-ink leading-[1.12] tracking-tight mb-6">
                Your automated <br />
                <span className="text-spruce-green italic">tech career</span> command center.
              </h1>

              <p className="text-base sm:text-lg text-foreground-muted leading-relaxed mb-8 max-w-lg">
                JobPrep crawls software engineering internship postings daily across curated GitHub repositories and LinkedIn. Enriched with Gemini skill extraction, 768-dimension semantic embeddings, and real-time SSE updates.
              </p>

              {/* Dual Primary CTAs: Explore Jobs + Sign in with Google */}
              <div className="flex flex-col sm:flex-row gap-3 max-w-md">
                <Link
                  href="/jobs"
                  className="inline-flex items-center justify-center gap-2 bg-spruce-green hover:bg-spruce-green-hover text-warm-ivory px-6 py-3 rounded text-sm font-medium shadow-sm transition-colors"
                >
                  Explore Jobs <ArrowRight size={15} />
                </Link>

                <a
                  href={authApi.googleLoginUrl("/jobs")}
                  className="inline-flex items-center justify-center gap-2.5 bg-background border border-slate-soft hover:border-spruce-green/50 text-slate-ink px-5 py-3 rounded text-sm font-medium transition-colors shadow-xs"
                >
                  <svg width="16" height="16" viewBox="0 0 18 18" aria-hidden="true">
                    <path fill="#4285F4" d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62Z"/>
                    <path fill="#34A853" d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.81.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.96v2.33A9 9 0 0 0 9 18Z"/>
                    <path fill="#FBBC05" d="M3.97 10.72A5.41 5.41 0 0 1 3.68 9c0-.6.1-1.18.29-1.72V4.95H.96A9 9 0 0 0 0 9c0 1.45.35 2.82.96 4.05l3.01-2.33Z"/>
                    <path fill="#EA4335" d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.59C13.46.89 11.43 0 9 0A9 9 0 0 0 .96 4.95l3.01 2.33C4.68 5.16 6.66 3.58 9 3.58Z"/>
                  </svg>
                  Sign in with Google
                </a>
              </div>

              {/* Social Proof Metrics Row */}
              <div className="grid grid-cols-3 gap-6 mt-10 pt-8 border-t border-slate-soft">
                <div>
                  <p className="text-2xl font-serif font-medium text-slate-ink">4+</p>
                  <p className="font-mono text-[10px] uppercase tracking-wider text-foreground-subtle mt-0.5">Scraped Repos</p>
                </div>
                <div>
                  <p className="text-2xl font-serif font-medium text-slate-ink">~125+</p>
                  <p className="font-mono text-[10px] uppercase tracking-wider text-foreground-subtle mt-0.5">Daily Roles</p>
                </div>
                <div>
                  <p className="text-2xl font-serif font-medium text-slate-ink">768d</p>
                  <p className="font-mono text-[10px] uppercase tracking-wider text-foreground-subtle mt-0.5">Vector Search</p>
                </div>
              </div>
            </div>

            {/* Right: Interactive Live Feed Card */}
            <div>
              <InteractiveLiveCard />
            </div>

          </div>
        </div>
      </section>

      {/* Feature Bento Grid */}
      <section id="features" className="py-20 border-t border-slate-soft bg-neutral-soft/30">
        <div className="max-w-6xl mx-auto px-6">
          <div className="text-center max-w-xl mx-auto mb-14">
            <span className="font-mono text-[10px] uppercase tracking-widest text-spruce-green font-semibold">
              Engineered for Quality
            </span>
            <h2 className="text-3xl font-serif font-medium text-slate-ink tracking-tight mt-2">
              From raw listings to verified intelligence.
            </h2>
            <p className="text-xs text-foreground-muted mt-2">
              Every job posting undergoes automated sanitization, content extraction, and multi-tier deduplication.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
            <BentoPipelineCard />
            <BentoSSECard />
            <BentoAIDemoCard />

            {/* Smart Categories Card */}
            <div className="rounded-xl border border-slate-soft bg-background p-6 hover:border-spruce-green/30 transition-all flex flex-col justify-between">
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <Layers size={18} className="text-amber-clay" />
                  <h3 className="font-serif text-base font-medium text-slate-ink">Smart Categorization</h3>
                </div>
                <p className="text-xs text-foreground-muted mb-4 leading-relaxed">
                  Automatically sorts companies into FAANG+, Quant finance, and high-growth tech categories with one-click remote filtering.
                </p>
                <div className="flex flex-wrap gap-1.5 pt-2">
                  <span className="px-2.5 py-1 rounded bg-neutral-soft border border-slate-soft text-slate-ink text-xs font-mono">FAANG+</span>
                  <span className="px-2.5 py-1 rounded bg-neutral-soft border border-slate-soft text-slate-ink text-xs font-mono">Quant</span>
                  <span className="px-2.5 py-1 rounded bg-spruce-green/10 text-spruce-green text-xs font-mono">Remote Only</span>
                </div>
              </div>
            </div>

            {/* Semantic Vector Search Card */}
            <div className="rounded-xl border border-slate-soft bg-background p-6 hover:border-spruce-green/30 transition-all flex flex-col justify-between">
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <Search size={18} className="text-spruce-green" />
                  <h3 className="font-serif text-base font-medium text-slate-ink">Semantic Vector Search</h3>
                </div>
                <p className="text-xs text-foreground-muted mb-4 leading-relaxed">
                  Search with natural language queries or resume snippets. Powered by pgvector and Gemini text-embedding-004 cosine distance.
                </p>
                <div className="bg-neutral-soft border border-slate-soft rounded-lg p-2.5 font-mono text-[10px] text-foreground-subtle">
                  SELECT * FROM jobs ORDER BY embedding &lt;=&gt; query_vector LIMIT 20
                </div>
              </div>
            </div>

            {/* Production Architecture Card */}
            <div className="rounded-xl border border-slate-soft bg-background p-6 hover:border-spruce-green/30 transition-all flex flex-col justify-between">
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <ShieldCheck size={18} className="text-amber-clay" />
                  <h3 className="font-serif text-base font-medium text-slate-ink">Production Grade Security</h3>
                </div>
                <p className="text-xs text-foreground-muted mb-4 leading-relaxed">
                  HttpOnly SameSite=Lax JWT cookies, Redis revocation denylists, Celery rate-limits, and double-submit CSRF defenses.
                </p>
                <div className="flex items-center gap-2 text-[10px] font-mono text-spruce-green">
                  <span className="w-1.5 h-1.5 rounded-full bg-spruce-green" /> 100% XSS &amp; CSRF Protected
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Footer Section */}
      <section className="py-20 border-t border-slate-soft">
        <div className="max-w-2xl mx-auto px-6 text-center">
          <h2 className="text-3xl font-serif font-medium text-slate-ink tracking-tight mb-4">
            Never miss an internship window again.
          </h2>
          <p className="text-sm text-foreground-muted mb-8 leading-relaxed">
            Gain immediate visibility into new software engineering roles the minute they are published.
          </p>
          <div className="flex flex-wrap justify-center gap-3">
            <Link
              href="/register"
              className="bg-spruce-green hover:bg-spruce-green-hover text-warm-ivory px-6 py-3 rounded text-sm font-medium transition-colors shadow-sm"
            >
              Create Free Account
            </Link>
            <Link
              href="/jobs"
              className="bg-background border border-slate-soft hover:border-spruce-green text-slate-ink px-6 py-3 rounded text-sm font-medium transition-colors shadow-xs"
            >
              Browse Public Board
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-soft py-8 bg-neutral-soft/20 text-xs">
        <div className="max-w-6xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="font-mono text-[10px] text-foreground-subtle uppercase tracking-wider">
            © 2026 JobPrep · Built with Next.js, FastAPI, Celery, Gemini
          </p>
          <div className="flex gap-4 text-foreground-muted">
            <Link href="/jobs" className="hover:text-spruce-green transition-colors">Jobs</Link>
            <Link href="/news" className="hover:text-spruce-green transition-colors">Radar</Link>
            <Link href="/login" className="hover:text-spruce-green transition-colors">Sign In</Link>
            <Link href="/register" className="hover:text-spruce-green transition-colors">Register</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
