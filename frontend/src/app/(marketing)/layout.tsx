import type { Metadata } from "next";
import Link from "next/link";
import { cookies } from "next/headers";
import ThemeToggle from "@/components/ThemeToggle";
import SkipLink from "@/components/SkipLink";
import MarketingMobileNav from "./MarketingMobileNav";
import { ButtonLink } from "@/components/ui/Button";
import { SITE_URL } from "@/lib/urls";
import type { User } from "@/lib/api";
import { INTERNAL_API_URL } from "@/lib/server-api";

export const dynamic = "force-dynamic";

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

async function getSessionUser(): Promise<User | null> {
  try {
    const cookieHeader = (await cookies()).toString();
    if (!cookieHeader || !cookieHeader.includes("access_token")) return null;
    const res = await fetch(`${INTERNAL_API_URL}/api/v1/auth/me`, {
      headers: { cookie: cookieHeader },
      cache: "no-store",
    });
    if (res.ok) return (await res.json()) as User;
    return null;
  } catch {
    return null;
  }
}

/**
 * Persistent marketing chrome, rendered on the server. The header adapts
 * for authenticated sessions vs. guest visitors.
 */
export default async function MarketingLayout({ children }: { children: React.ReactNode }) {
  const user = await getSessionUser();
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

      <SkipLink />
      <header className="fixed top-0 inset-x-0 z-50 backdrop-blur-md bg-background/85 border-b border-slate-soft">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link
            href="/"
            className="font-serif text-xl font-medium tracking-tight text-slate-ink hover:text-spruce-green transition-colors"
          >
            JobPrep
          </Link>

          <nav aria-label="Main" className="hidden md:flex items-center gap-6 text-xs font-medium text-foreground-muted">
            <Link href="/jobs" className="hover:text-slate-ink transition-colors font-medium">Job Board</Link>
            <Link href="/news" className="hover:text-slate-ink transition-colors font-medium">Tech Radar</Link>
            <Link href="/#features" className="hover:text-slate-ink transition-colors">Features</Link>
            <Link href="/#demo" className="hover:text-slate-ink transition-colors">AI Intelligence</Link>
          </nav>

          <div className="flex items-center gap-3">
            <ThemeToggle />
            {user ? (
              <>
                <span className="hidden sm:inline font-sans text-xs text-foreground-muted truncate max-w-44 border border-slate-soft px-3 py-1 rounded-full bg-neutral-soft" title={user.email}>
                  {user.email}
                </span>
                <ButtonLink href="/jobs" size="sm" className="rounded-full shadow-xs">
                  Job Board
                </ButtonLink>
                <MarketingMobileNav isLoggedIn />
              </>
            ) : (
              <>
                <span className="hidden sm:inline">
                  <ButtonLink href="/login" variant="ghost" size="sm" className="rounded-full">
                    Sign In
                  </ButtonLink>
                </span>
                <ButtonLink href="/register" size="sm" className="rounded-full shadow-xs">
                  Get Started
                </ButtonLink>
                <MarketingMobileNav />
              </>
            )}
          </div>
        </div>
      </header>

      {/* Skip-link target; programmatic focus only, so no ring around the page. */}
      <main id="main" tabIndex={-1} className="focus:outline-none">
        {children}
      </main>

      <footer className="border-t border-slate-soft py-8 bg-neutral-soft/20 text-xs">
        <div className="max-w-6xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="font-mono text-2xs text-foreground-subtle uppercase tracking-wider">
            © 2026 JobPrep · Built with Next.js, FastAPI, Celery, Gemini
          </p>
          <nav aria-label="Footer" className="flex gap-4 text-foreground-muted">
            <Link href="/jobs" className="hover:text-spruce-green transition-colors">Jobs</Link>
            <Link href="/news" className="hover:text-spruce-green transition-colors">Radar</Link>
            {!user && (
              <>
                <Link href="/login" className="hover:text-spruce-green transition-colors">Sign In</Link>
                <Link href="/register" className="hover:text-spruce-green transition-colors">Register</Link>
              </>
            )}
          </nav>
        </div>
      </footer>
    </div>
  );
}
