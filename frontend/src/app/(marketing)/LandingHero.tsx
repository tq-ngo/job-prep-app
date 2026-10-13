import Link from "next/link";
import { ArrowRight, Layers, Search, ShieldCheck } from "lucide-react";
import { googleLoginUrl } from "@/lib/urls";
import {
  BentoAIDemoCard,
  BentoPipelineCard,
  BentoSSECard,
  InteractiveLiveCard,
} from "./LandingDemos";

export interface PublicStats {
  active_jobs: number;
  added_24h: number;
  companies: number;
  last_crawl_at: string | null;
}

const lastCrawlFormat = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "UTC",
  timeZoneName: "short",
});

/**
 * Server component: the copy and layout ship as static HTML (regenerated
 * every few minutes with fresh stats). It used to be one "use client" tree,
 * so the whole page — static sections included — shipped as JS and hydrated.
 */
export default function LandingHero({ stats }: { stats: PublicStats | null }) {
  const metrics = stats
    ? [
        { value: stats.active_jobs.toLocaleString("en-US"), label: "Open roles" },
        { value: stats.companies.toLocaleString("en-US"), label: "Companies" },
        { value: stats.added_24h.toLocaleString("en-US"), label: "Added in 24h" },
      ]
    : [
        { value: "4", label: "GitHub repos" },
        { value: "6h", label: "Crawl cadence" },
        { value: "768d", label: "Vector search" },
      ];

  return (
    <>
      {/* Hero Section */}
      <section className="pt-32 pb-16 lg:pt-40 lg:pb-24">
        <div className="max-w-6xl mx-auto px-6">
          <div className="grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">

            {/* Left: Editorial Copy */}
            <div>
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-spruce-green/10 border border-spruce-green/20 mb-6">
                <div className="w-1.5 h-1.5 rounded-full bg-spruce-green animate-pulse" />
                <span className="font-mono text-[11px] uppercase tracking-widest text-spruce-green font-semibold">
                  {stats && stats.added_24h > 0
                    ? `${stats.added_24h.toLocaleString("en-US")} new roles in the last 24h`
                    : "Crawled every 6 hours from GitHub & LinkedIn"}
                </span>
              </div>

              <h1 className="text-4xl sm:text-5xl lg:text-6xl font-serif font-medium text-slate-ink leading-[1.12] tracking-tight mb-6">
                Your automated <br />
                <span className="text-spruce-green italic">tech career</span> command center.
              </h1>

              <p className="text-base sm:text-lg text-foreground-muted leading-relaxed mb-8 max-w-lg">
                JobPrep crawls software engineering internship postings across curated GitHub repositories and LinkedIn, then enriches them with Gemini skill extraction, semantic search, and live updates.
              </p>

              <div className="flex flex-col sm:flex-row gap-3 max-w-md">
                <a
                  href={googleLoginUrl("/jobs")}
                  className="inline-flex items-center justify-center gap-2.5 bg-spruce-green hover:bg-spruce-green-hover text-warm-ivory px-5 py-3 rounded text-sm font-medium shadow-sm transition-colors"
                >
                  <svg width="16" height="16" viewBox="0 0 18 18" aria-hidden="true" className="bg-white rounded-sm p-px">
                    <path fill="#4285F4" d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62Z"/>
                    <path fill="#34A853" d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.81.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.96v2.33A9 9 0 0 0 9 18Z"/>
                    <path fill="#FBBC05" d="M3.97 10.72A5.41 5.41 0 0 1 3.68 9c0-.6.1-1.18.29-1.72V4.95H.96A9 9 0 0 0 0 9c0 1.45.35 2.82.96 4.05l3.01-2.33Z"/>
                    <path fill="#EA4335" d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.59C13.46.89 11.43 0 9 0A9 9 0 0 0 .96 4.95l3.01 2.33C4.68 5.16 6.66 3.58 9 3.58Z"/>
                  </svg>
                  Sign in with Google
                </a>

                {/* The board requires an account; say so rather than promise
                    a "public board" that bounces to /login. */}
                <Link
                  href="/jobs"
                  className="inline-flex items-center justify-center gap-2 bg-background border border-slate-soft hover:border-spruce-green/50 text-slate-ink px-6 py-3 rounded text-sm font-medium transition-colors shadow-xs"
                >
                  Open the job board <ArrowRight size={15} />
                </Link>
              </div>
              <p className="mt-3 text-xs text-foreground-subtle">Free account required to browse listings.</p>

              {/* Metrics Row */}
              <dl className="grid grid-cols-3 gap-6 mt-10 pt-8 border-t border-slate-soft">
                {metrics.map(({ value, label }) => (
                  <div key={label} className="flex flex-col-reverse">
                    <dt className="font-mono text-[11px] uppercase tracking-wider text-foreground-subtle mt-0.5">{label}</dt>
                    <dd className="text-2xl font-serif font-medium text-slate-ink">{value}</dd>
                  </div>
                ))}
              </dl>
              {stats?.last_crawl_at && (
                <p className="mt-3 font-mono text-[11px] text-foreground-subtle">
                  Last crawl:{" "}
                  <time dateTime={stats.last_crawl_at}>{lastCrawlFormat.format(new Date(stats.last_crawl_at))}</time>
                </p>
              )}
            </div>

            {/* Right: Interactive preview (client island) */}
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
            <span className="font-mono text-[11px] uppercase tracking-widest text-spruce-green font-semibold">
              Engineered for Quality
            </span>
            <h2 className="text-3xl font-serif font-medium text-slate-ink tracking-tight mt-2">
              From raw listings to verified intelligence.
            </h2>
            <p className="text-sm text-foreground-muted mt-2">
              Every job posting is sanitized, its full description extracted, and duplicates across sources linked to one listing.
            </p>
          </div>

          <div id="demo" className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
            <BentoPipelineCard />
            <BentoSSECard initialCount={stats ? stats.added_24h : null} />
            <BentoAIDemoCard />

            {/* Smart Categories Card */}
            <div className="rounded-xl border border-slate-soft bg-background p-6 hover:border-spruce-green/30 transition-all flex flex-col justify-between">
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <Layers size={18} className="text-amber-clay" />
                  <h3 className="font-serif text-base font-medium text-slate-ink">Smart Categorization</h3>
                </div>
                <p className="text-xs text-foreground-muted mb-4 leading-relaxed">
                  Sorts companies into FAANG+, quant finance, and everything else, with one-click remote filtering.
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
                  Search with natural language or a resume snippet, ranked by pgvector cosine distance over Gemini embeddings.
                </p>
                <div className="bg-neutral-soft border border-slate-soft rounded-lg p-2.5 font-mono text-[11px] text-foreground-subtle">
                  SELECT * FROM jobs ORDER BY embedding &lt;=&gt; query_vector LIMIT 20
                </div>
              </div>
            </div>

            {/* Security Card */}
            <div className="rounded-xl border border-slate-soft bg-background p-6 hover:border-spruce-green/30 transition-all flex flex-col justify-between">
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <ShieldCheck size={18} className="text-amber-clay" />
                  <h3 className="font-serif text-base font-medium text-slate-ink">Security by Default</h3>
                </div>
                <p className="text-xs text-foreground-muted mb-4 leading-relaxed">
                  Google sign-in with PKCE, HttpOnly SameSite=Lax session cookies, rotating refresh tokens with reuse detection, and double-submit CSRF.
                </p>
                <div className="flex items-center gap-2 text-[11px] font-mono text-spruce-green">
                  <span className="w-1.5 h-1.5 rounded-full bg-spruce-green" /> No tokens in localStorage
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 border-t border-slate-soft">
        <div className="max-w-2xl mx-auto px-6 text-center">
          <h2 className="text-3xl font-serif font-medium text-slate-ink tracking-tight mb-4">
            Never miss an internship window again.
          </h2>
          <p className="text-sm text-foreground-muted mb-8 leading-relaxed">
            See new software engineering roles soon after they are posted.
          </p>
          <div className="flex flex-wrap justify-center gap-3">
            <Link
              href="/register"
              className="bg-spruce-green hover:bg-spruce-green-hover text-warm-ivory px-6 py-3 rounded text-sm font-medium transition-colors shadow-sm"
            >
              Create free account
            </Link>
            <Link
              href="/login"
              className="bg-background border border-slate-soft hover:border-spruce-green text-slate-ink px-6 py-3 rounded text-sm font-medium transition-colors shadow-xs"
            >
              Sign in to browse
            </Link>
          </div>
        </div>
      </section>
    </>
  );
}
