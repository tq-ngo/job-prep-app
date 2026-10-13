import type { Metadata } from "next";
import Link from "next/link";
import ThemeToggle from "@/components/ThemeToggle";
import { SITE_URL } from "@/lib/urls";

const TITLE = "JobPrep — Automated Tech Career Command Center";
const SHORT_DESCRIPTION =
  "SWE internship listings from GitHub and LinkedIn, with AI skill extraction and live updates.";

export const metadata: Metadata = {
  title: TITLE,
  description:
    "JobPrep aggregates SWE internship listings from GitHub repos and LinkedIn, enriches them with AI-powered skill extraction via Gemini, and delivers real-time updates. Never miss a role.",
  keywords: [
    "software engineer internship",
    "SWE intern jobs",
    "tech career",
    "job board",
    "automated job aggregator",
    "AI job matching",
  ],
  // og:image / twitter:image come from ./opengraph-image.tsx.
  openGraph: {
    title: TITLE,
    description: SHORT_DESCRIPTION,
    type: "website",
    url: "/",
    siteName: "JobPrep",
  },
  twitter: {
    card: "summary_large_image",
    title: TITLE,
    description: SHORT_DESCRIPTION,
  },
};

/**
 * Persistent marketing chrome, rendered on the server. The header used to
 * live inside the client-only LandingHero, so it shipped as JS and wasn't
 * shared by any other marketing route.
 */
export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  const jsonLd = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "WebSite",
        "@id": `${SITE_URL}/#website`,
        url: `${SITE_URL}/`,
        name: "JobPrep",
        description: "Automated SWE Internship Aggregator & AI Career Command Center",
      },
      {
        "@type": "SoftwareApplication",
        "@id": `${SITE_URL}/#application`,
        name: "JobPrep Platform",
        applicationCategory: "BusinessApplication",
        operatingSystem: "Web",
        offers: { "@type": "Offer", price: "0", priceCurrency: "USD" },
        featureList: [
          "Automated GitHub and LinkedIn crawling",
          "3-layer deduplication pipeline (LRU, Redis, PostgreSQL)",
          "Gemini skill extraction and pgvector semantic search",
          "Live Server-Sent Events updates",
        ],
      },
    ],
  };

  return (
    <div className="min-h-screen bg-background text-foreground font-sans">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      <header className="fixed top-0 inset-x-0 z-50 backdrop-blur-md bg-background/85 border-b border-slate-soft">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link
            href="/"
            className="font-serif text-xl font-medium tracking-tight text-slate-ink hover:text-spruce-green transition-colors"
          >
            JobPrep
          </Link>

          <nav aria-label="Main" className="hidden md:flex items-center gap-6 text-xs font-medium text-foreground-muted">
            <Link href="/#features" className="hover:text-slate-ink transition-colors">Features</Link>
            <Link href="/#demo" className="hover:text-slate-ink transition-colors">AI Intelligence</Link>
            <Link href="/news" className="hover:text-slate-ink transition-colors">Tech Radar</Link>
            <Link href="/jobs" className="hover:text-slate-ink transition-colors">Job Board</Link>
          </nav>

          <div className="flex items-center gap-3">
            <ThemeToggle />
            <Link href="/login" className="text-xs font-medium text-foreground-muted hover:text-slate-ink transition-colors px-2 py-1">
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

      <main>{children}</main>

      <footer className="border-t border-slate-soft py-8 bg-neutral-soft/20 text-xs">
        <div className="max-w-6xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="font-mono text-[11px] text-foreground-subtle uppercase tracking-wider">
            © 2026 JobPrep · Built with Next.js, FastAPI, Celery, Gemini
          </p>
          <nav aria-label="Footer" className="flex gap-4 text-foreground-muted">
            <Link href="/jobs" className="hover:text-spruce-green transition-colors">Jobs</Link>
            <Link href="/news" className="hover:text-spruce-green transition-colors">Radar</Link>
            <Link href="/login" className="hover:text-spruce-green transition-colors">Sign In</Link>
            <Link href="/register" className="hover:text-spruce-green transition-colors">Register</Link>
          </nav>
        </div>
      </footer>
    </div>
  );
}
