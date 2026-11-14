import { cookies } from "next/headers";
import LandingHero, { type PublicStats } from "./LandingHero";
import SignedInHome from "./SignedInHome";
import type { User } from "@/lib/api";
import { INTERNAL_API_URL } from "@/lib/server-api";

export const dynamic = "force-dynamic";

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

export default async function HomePage() {
  const [stats, user] = await Promise.all([getStats(), getSessionUser()]);
  if (user) {
    return <SignedInHome user={user} stats={stats} />;
  }
  return <LandingHero stats={stats} />;
}
