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
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-primary-container border border-primary/20 mb-6">
                <div className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse motion-reduce:animate-none" />
                <span className="font-mono text-label-small uppercase tracking-widest text-on-primary-container font-semibold">
                  {stats && stats.added_24h > 0
                    ? `${stats.added_24h.toLocaleString("en-US")} new roles in the last 24h`
                    : "Crawled every 6 hours from GitHub & LinkedIn"}
                </span>
              </div>

              <h1 className="text-display-medium sm:text-display-large font-serif font-medium text-on-surface leading-[1.12] tracking-tight mb-6">
                Your automated <br />
                <span className="text-primary italic">tech career</span> command center.
              </h1>

              <p className="text-body-large text-on-surface-variant leading-relaxed mb-8 max-w-lg">
                JobPrep crawls software engineering internship postings across curated GitHub repositories and LinkedIn, then enriches them with Gemini skill extraction, semantic search, and live updates.
              </p>

              <div className="flex flex-col sm:flex-row gap-3 max-w-md">
                {/* native: an API route, so a full navigation, not client routing. */}
                <ButtonLink
                  href={googleLoginUrl("/jobs")}
                  native
                  variant="filled"
                  size="lg"
                  icon={<GoogleIcon size={16} className="bg-surface-container-lowest rounded-xs p-px" />}
                >
                  Sign in with Google
                </ButtonLink>

                {/* The board requires an account; say so rather than promise
                    a "public board" that bounces to /login. */}
                <ButtonLink href="/jobs" variant="outlined" size="lg">
                  Open the job board <ArrowRight size={15} aria-hidden="true" />
                </ButtonLink>
              </div>
              <p className="mt-3 text-body-small text-on-surface-variant">Free account required to browse listings.</p>

              {/* Metrics Row */}
              <dl className="grid grid-cols-3 gap-6 mt-10 pt-8 border-t border-outline-variant">
                {metrics.map(({ value, label }) => (
                  <div key={label} className="flex flex-col-reverse">
                    <dt className="font-mono text-label-small uppercase tracking-wider text-on-surface-variant mt-0.5">{label}</dt>
                    <dd className="text-headline-small font-serif font-medium text-on-surface">{value}</dd>
                  </div>
                ))}
              </dl>
              {stats?.last_crawl_at && (
                <p className="mt-3 font-mono text-label-small text-on-surface-variant">
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
      <section id="features" className="py-20 border-t border-outline-variant bg-surface-container-low/50">
        <div className="max-w-6xl mx-auto px-6">
          <div className="text-center max-w-xl mx-auto mb-14">
            <span className="font-mono text-label-small uppercase tracking-widest text-primary font-semibold">
              Engineered for Quality
            </span>
            <h2 className="text-headline-large font-serif font-medium text-on-surface tracking-tight mt-2">
              From raw listings to verified intelligence.
            </h2>
            <p className="text-body-medium text-on-surface-variant mt-2">
              Every job posting is sanitized, its full description extracted, and duplicates across sources linked to one listing.
            </p>
          </div>

          <div id="demo" className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
            <BentoPipelineCard />
            <BentoSSECard initialCount={stats ? stats.added_24h : null} />
            <BentoAIDemoCard />

            {/* Smart Categories Card */}
            <Card tone="elevated" interactive className="flex flex-col justify-between">
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <Layers size={18} className="text-primary" />
                  <h3 className="font-serif text-title-medium font-medium text-on-surface">Smart Categorization</h3>
                </div>
                <p className="text-body-small text-on-surface-variant mb-4 leading-relaxed">
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
            <Card tone="elevated" interactive className="flex flex-col justify-between">
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <Search size={18} className="text-primary" />
                  <h3 className="font-serif text-title-medium font-medium text-on-surface">Semantic Vector Search</h3>
                </div>
                <p className="text-body-small text-on-surface-variant mb-4 leading-relaxed">
                  Search with natural language or a resume snippet, ranked by pgvector cosine distance over Gemini embeddings.
                </p>
                <div className="bg-surface-container-low border border-outline-variant rounded-sm p-2.5 font-mono text-label-small text-on-surface-variant">
                  SELECT * FROM jobs ORDER BY embedding &lt;=&gt; query_vector LIMIT 20
                </div>
              </div>
            </Card>

            {/* Security Card */}
            <Card tone="elevated" interactive className="flex flex-col justify-between">
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <ShieldCheck size={18} className="text-primary" />
                  <h3 className="font-serif text-title-medium font-medium text-on-surface">Security by Default</h3>
                </div>
                <p className="text-body-small text-on-surface-variant mb-4 leading-relaxed">
                  Google sign-in with PKCE, HttpOnly SameSite=Lax session cookies, rotating refresh tokens with reuse detection, and double-submit CSRF.
                </p>
                <div className="flex items-center gap-2 text-label-small font-mono text-primary">
                  <span className="w-1.5 h-1.5 rounded-full bg-primary" /> No tokens in localStorage
                </div>
              </div>
            </Card>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 border-t border-outline-variant">
        <div className="max-w-2xl mx-auto px-6 text-center">
          <h2 className="text-headline-large font-serif font-medium text-on-surface tracking-tight mb-4">
            Never miss an internship window again.
          </h2>
          <p className="text-body-medium text-on-surface-variant mb-8 leading-relaxed">
            See new software engineering roles soon after they are posted.
          </p>
          <div className="flex flex-wrap justify-center gap-3">
            <ButtonLink href="/register" variant="filled" size="lg">
              Create free account
            </ButtonLink>
            <ButtonLink href="/login" variant="outlined" size="lg">
              Sign in to browse
            </ButtonLink>
          </div>
        </div>
      </section>
    </>
  );
}
