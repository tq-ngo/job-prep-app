import { InteractiveLiveCard, PipelineHighlights } from "./LandingDemos";
import { MarketingHeroActions } from "./MarketingAuthActions";

export interface PlatformStats {
  active_jobs: number;
  added_24h: number;
  companies: number;
  last_crawl_at?: string | null;
}

function formatCount(value: number | undefined): string {
  return typeof value === "number" ? value.toLocaleString("en-US") : "—";
}

export default function LandingHero({ stats }: { stats: PlatformStats | null }) {
  const metrics = [
    { label: "Active internships", value: formatCount(stats?.active_jobs) },
    { label: "Added in 24h", value: formatCount(stats?.added_24h) },
    { label: "Hiring companies", value: formatCount(stats?.companies) },
  ];

  return (
    <div className="max-w-app mx-auto px-4 sm:px-6">
      <section className="pt-12 pb-16 sm:pt-20 sm:pb-24">
        <div className="max-w-3xl">
          <p className="text-label-large font-medium text-primary mb-4">
            Software engineering, ML, and quant internships
          </p>
          <h1 className="text-display-small sm:text-display-large font-semibold text-on-surface tracking-tight text-balance">
            Every open SWE internship in one live, deduplicated feed
          </h1>
          <p className="text-body-large text-on-surface-variant mt-5 max-w-2xl leading-relaxed">
            JobPrep crawls GitHub and LinkedIn every hour, merges cross-posted listings, extracts skills and visa requirements, and streams new openings to your board as they land.
          </p>

          <div className="mt-8">
            <MarketingHeroActions primaryLabel="Create free account" />
          </div>
        </div>

        <dl className="grid grid-cols-3 gap-6 max-w-xl mt-12 pt-8 border-t border-outline-variant">
          {metrics.map(({ label, value }) => (
            <div key={label}>
              <dd className="font-mono text-headline-small sm:text-headline-medium font-semibold text-on-surface tabular-nums">
                {value}
              </dd>
              <dt className="text-label-medium text-on-surface-variant mt-1">{label}</dt>
            </div>
          ))}
        </dl>
      </section>

      <section id="demo" className="scroll-mt-20 pb-20 sm:pb-24">
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-6">
          <div>
            <h2 className="text-headline-medium font-semibold text-on-surface">Split-pane job board</h2>
            <p className="text-body-medium text-on-surface-variant mt-1">
              Scan titles, pay, and extracted skills on the left while reading the full description on the right.
            </p>
          </div>
        </div>
        <InteractiveLiveCard />
      </section>

      <section id="features" className="scroll-mt-20 pb-20 sm:pb-24">
        <div className="max-w-2xl mb-8">
          <h2 className="text-headline-medium font-semibold text-on-surface">Built for fast internship search</h2>
          <p className="text-body-medium text-on-surface-variant mt-2">
            Less tab-switching between spreadsheets and job boards, more time applying while roles are still open.
          </p>
        </div>
        <PipelineHighlights newLast24h={stats?.added_24h ?? null} />
      </section>

      <section className="pb-20 sm:pb-24">
        <div className="rounded-xl bg-surface-container-low border border-outline-variant p-8 sm:p-10 flex flex-col sm:flex-row sm:items-center justify-between gap-6">
          <div className="max-w-xl">
            <h2 className="text-headline-small sm:text-headline-medium font-semibold text-on-surface">
              Track your skills and start applying
            </h2>
            <p className="text-body-medium text-on-surface-variant mt-2">
              Sign in to browse the live internship feed, save your core skills, and follow daily tech news.
            </p>
          </div>
          <div className="shrink-0">
            <MarketingHeroActions primaryLabel="Get started" />
          </div>
        </div>
      </section>
    </div>
  );
}
