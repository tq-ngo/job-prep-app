import { ArrowRight, Layers, Search, ShieldCheck } from "lucide-react";
import { googleLoginUrl } from "@/lib/urls";
import Badge from "@/components/ui/Badge";
import { ButtonLink } from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import GoogleIcon from "@/components/ui/GoogleIcon";
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
                <span className="font-mono text-2xs uppercase tracking-widest text-spruce-green font-semibold">
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
                {/* native: an API route, so a full navigation, not client routing. */}
                <ButtonLink
                  href={googleLoginUrl("/jobs")}
                  native
                  size="lg"
                  icon={<GoogleIcon size={16} className="bg-white rounded-sm p-px" />}
                >
                  Sign in with Google
                </ButtonLink>

                {/* The board requires an account; say so rather than promise
                    a "public board" that bounces to /login. */}
                <ButtonLink href="/jobs" variant="secondary" size="lg">
                  Open the job board <ArrowRight size={15} aria-hidden="true" />
                </ButtonLink>
              </div>
              <p className="mt-3 text-xs text-foreground-subtle">Free account required to browse listings.</p>

              {/* Metrics Row */}
              <dl className="grid grid-cols-3 gap-6 mt-10 pt-8 border-t border-slate-soft">
                {metrics.map(({ value, label }) => (
                  <div key={label} className="flex flex-col-reverse">
                    <dt className="font-mono text-2xs uppercase tracking-wider text-foreground-subtle mt-0.5">{label}</dt>
                    <dd className="text-2xl font-serif font-medium text-slate-ink">{value}</dd>
                  </div>
                ))}
              </dl>
              {stats?.last_crawl_at && (
                <p className="mt-3 font-mono text-2xs text-foreground-subtle">
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
            <span className="font-mono text-2xs uppercase tracking-widest text-spruce-green font-semibold">
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
            <Card interactive className="flex flex-col justify-between">
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <Layers size={18} className="text-amber-clay" />
                  <h3 className="font-serif text-base font-medium text-slate-ink">Smart Categorization</h3>
                </div>
                <p className="text-xs text-foreground-muted mb-4 leading-relaxed">
                  Sorts companies into FAANG+, quant finance, and everything else, with one-click remote filtering.
                </p>
                <div className="flex flex-wrap gap-1.5 pt-2">
                  <Badge size="md">FAANG+</Badge>
                  <Badge size="md">Quant</Badge>
                  <Badge size="md" variant="skill">Remote Only</Badge>
                </div>
              </div>
            </Card>

            {/* Semantic Vector Search Card */}
            <Card interactive className="flex flex-col justify-between">
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <Search size={18} className="text-spruce-green" />
                  <h3 className="font-serif text-base font-medium text-slate-ink">Semantic Vector Search</h3>
                </div>
                <p className="text-xs text-foreground-muted mb-4 leading-relaxed">
                  Search with natural language or a resume snippet, ranked by pgvector cosine distance over Gemini embeddings.
                </p>
                <div className="bg-neutral-soft border border-slate-soft rounded-card p-2.5 font-mono text-2xs text-foreground-subtle">
                  SELECT * FROM jobs ORDER BY embedding &lt;=&gt; query_vector LIMIT 20
                </div>
              </div>
            </Card>

            {/* Security Card */}
            <Card interactive className="flex flex-col justify-between">
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <ShieldCheck size={18} className="text-amber-clay" />
                  <h3 className="font-serif text-base font-medium text-slate-ink">Security by Default</h3>
                </div>
                <p className="text-xs text-foreground-muted mb-4 leading-relaxed">
                  Google sign-in with PKCE, HttpOnly SameSite=Lax session cookies, rotating refresh tokens with reuse detection, and double-submit CSRF.
                </p>
                <div className="flex items-center gap-2 text-2xs font-mono text-spruce-green">
                  <span className="w-1.5 h-1.5 rounded-full bg-spruce-green" /> No tokens in localStorage
                </div>
              </div>
            </Card>
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
            <ButtonLink href="/register" size="lg">
              Create free account
            </ButtonLink>
            <ButtonLink href="/login" variant="secondary" size="lg">
              Sign in to browse
            </ButtonLink>
          </div>
        </div>
      </section>
    </>
  );
}
