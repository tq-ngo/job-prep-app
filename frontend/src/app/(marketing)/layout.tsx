import type { Metadata } from "next";
import Link from "next/link";
import SkipLink from "@/components/SkipLink";
import ThemeToggle from "@/components/ThemeToggle";
import { ButtonLink } from "@/components/ui/Button";
import MarketingMobileNav from "./MarketingMobileNav";

export const metadata: Metadata = {
  title: {
    default: "JobPrep — Software engineering internships in one feed",
    template: "%s | JobPrep",
  },
  description:
    "Software engineering, ML, and quant internships aggregated hourly from GitHub and LinkedIn with skill extraction, visa sponsorship tags, and live feed updates.",
  openGraph: {
    title: "JobPrep — Software engineering internships in one feed",
    description:
      "Software engineering, ML, and quant internships aggregated hourly from GitHub and LinkedIn with skill extraction and live feed updates.",
    type: "website",
    siteName: "JobPrep",
  },
  twitter: {
    card: "summary_large_image",
    title: "JobPrep — Software engineering internships in one feed",
    description:
      "Software engineering, ML, and quant internships aggregated hourly from GitHub and LinkedIn.",
  },
  robots: { index: true, follow: true },
};

const navLinks = [
  { href: "/#features", label: "Features" },
  { href: "/#demo", label: "Live preview" },
];

export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col bg-surface text-on-surface">
      <SkipLink />

      <header className="sticky top-0 z-40 h-14 bg-surface/95 backdrop-blur-md border-b border-outline-variant">
        <div className="max-w-app mx-auto h-full px-4 sm:px-6 flex items-center justify-between gap-4">
          <Link
            href="/"
            className="text-title-large font-semibold tracking-tight text-on-surface hover:text-primary transition-colors"
          >
            JobPrep
          </Link>

          <nav aria-label="Primary" className="hidden md:flex items-center gap-6">
            {navLinks.map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                className="text-label-large font-medium text-on-surface-variant hover:text-on-surface transition-colors"
              >
                {label}
              </Link>
            ))}
          </nav>

          <div className="flex items-center gap-2">
            <ThemeToggle />
            <div className="hidden md:flex items-center gap-2">
              <ButtonLink href="/login" variant="text" size="sm">
                Sign in
              </ButtonLink>
              <ButtonLink href="/register" variant="filled" size="sm">
                Get started
              </ButtonLink>
            </div>
            <MarketingMobileNav links={navLinks} />
          </div>
        </div>
      </header>

      <main id="main" tabIndex={-1} className="flex-1 focus:outline-none">
        {children}
      </main>

      <footer className="border-t border-outline-variant bg-surface-container-low">
        <div className="max-w-app mx-auto px-4 sm:px-6 py-8 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
            <span className="text-title-medium font-semibold text-on-surface">JobPrep</span>
            <p className="text-body-small text-on-surface-variant">
              Hourly software engineering internship listings from GitHub and LinkedIn.
            </p>
          </div>
          <nav aria-label="Footer" className="flex items-center gap-4 text-label-medium text-on-surface-variant">
            <Link href="/jobs" className="hover:text-on-surface transition-colors">
              Job board
            </Link>
            <Link href="/news" className="hover:text-on-surface transition-colors">
              Tech news
            </Link>
            <Link href="/login" className="hover:text-on-surface transition-colors">
              Sign in
            </Link>
          </nav>
        </div>
      </footer>
    </div>
  );
}
