import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "JobPrep — Automated Tech Career Command Center",
  description:
    "JobPrep aggregates SWE internship listings from GitHub repos and LinkedIn, enriches them with AI-powered skill extraction via Gemini, and delivers real-time updates via SSE. Never miss a role.",
  keywords: [
    "software engineer internship",
    "SWE intern jobs",
    "tech career",
    "job board",
    "automated job aggregator",
    "AI job matching",
  ],
  openGraph: {
    title: "JobPrep — Automated Tech Career Command Center",
    description:
      "Aggregates 125+ SWE intern roles daily from GitHub and LinkedIn. AI-powered skill extraction and real-time updates.",
    type: "website",
    url: "/",
    siteName: "JobPrep",
  },
  twitter: {
    card: "summary_large_image",
    title: "JobPrep — Automated Tech Career Command Center",
    description:
      "Aggregates 125+ SWE intern roles daily from GitHub and LinkedIn. AI-powered skill extraction and real-time updates.",
  },
};

export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  const jsonLd = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "WebSite",
        "@id": "https://jobprep.app/#website",
        "url": "https://jobprep.app/",
        "name": "JobPrep",
        "description": "Automated SWE Internship Aggregator & AI Career Command Center",
      },
      {
        "@type": "SoftwareApplication",
        "@id": "https://jobprep.app/#application",
        "name": "JobPrep Platform",
        "applicationCategory": "BusinessApplication",
        "operatingSystem": "Web",
        "offers": {
          "@type": "Offer",
          "price": "0",
          "priceCurrency": "USD",
        },
        "featureList": [
          "Automated daily GitHub and LinkedIn scraping",
          "3-Layer deduplication pipeline (LRU, Redis, PostgreSQL)",
          "Gemini skill intelligence and 768-dim pgvector semantic search",
          "Live real-time Server-Sent Events updates",
        ],
      },
    ],
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      {children}
    </>
  );
}
