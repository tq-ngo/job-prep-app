import { INTERNAL_API_URL } from "@/lib/server-api";
import LandingHero, { type PlatformStats } from "./LandingHero";

// Public marketing landing page: statically regenerated every 5 minutes (300s ISR).
// Never read cookies or user sessions here so the page stays 100% cacheable and public.
export const revalidate = 300;

async function getStats(): Promise<PlatformStats | null> {
  try {
    const res = await fetch(`${INTERNAL_API_URL}/api/v1/stats/overview`, {
      next: { revalidate: 300 },
      signal: AbortSignal.timeout(3000),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export default async function HomePage() {
  const stats = await getStats();
  return <LandingHero stats={stats} />;
}
