import LandingHero, { type PublicStats } from "./LandingHero";
import { INTERNAL_API_URL } from "@/lib/server-api";

// Statically generated, then regenerated at most every 5 minutes (ISR) so
// the live numbers stay fresh without rendering per request.
const STATS_REVALIDATE_SECONDS = 300;

async function getStats(): Promise<PublicStats | null> {
  try {
    const res = await fetch(`${INTERNAL_API_URL}/api/v1/stats/`, {
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
