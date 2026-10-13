import LandingHero, { type PublicStats } from "./LandingHero";

// Statically generated, then regenerated at most every 5 minutes (ISR) so
// the live numbers stay fresh without rendering per request.
const STATS_REVALIDATE_SECONDS = 300;

async function getStats(): Promise<PublicStats | null> {
  const apiUrl = process.env.INTERNAL_API_URL || "http://localhost:8000";
  try {
    const res = await fetch(`${apiUrl}/api/v1/stats/`, {
      next: { revalidate: STATS_REVALIDATE_SECONDS },
    });
    return res.ok ? ((await res.json()) as PublicStats) : null;
  } catch {
    // The API isn't reachable at `next build` time; render the static
    // fallback and pick up real numbers on the first revalidation.
    return null;
  }
}

export default async function MarketingPage() {
  return <LandingHero stats={await getStats()} />;
}
