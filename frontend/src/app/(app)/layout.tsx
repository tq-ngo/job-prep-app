import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";
import DashboardNavbar from "@/components/DashboardNavbar";
import SkipLink from "@/components/SkipLink";
import { AuthProvider } from "@/context/AuthContext";
import type { User } from "@/lib/api";
import { PATHNAME_HEADER, SESSION_INVALID_REASON } from "@/proxy";
import { INTERNAL_API_URL } from "@/lib/server-api";

/**
 * Resolve the signed-in user on the server so the first paint is correct.
 *
 * proxy.ts has already verified the access token's signature before this
 * renders. This call is the authoritative check against the API (revocation,
 * disabled accounts); undefined means "unknown" and the client retries.
 */
async function getInitialUser(): Promise<User | null | undefined> {
  const cookieHeader = (await cookies()).toString();
  if (!cookieHeader) return null;
  try {
    const res = await fetch(`${INTERNAL_API_URL}/api/v1/auth/me`, {
      headers: { cookie: cookieHeader },
      cache: "no-store",
    });
    if (res.status === 401) return null;
    return res.ok ? ((await res.json()) as User) : undefined;
  } catch {
    return undefined;
  }
}

export default async function ProtectedLayout({ children }: { children: React.ReactNode }) {
  const initialUser = await getInitialUser();
  if (initialUser === null) {
    const headerList = await headers();
    const pathname = headerList.get(PATHNAME_HEADER) || "/jobs";
    redirect(`/login?next=${encodeURIComponent(pathname)}&reason=${SESSION_INVALID_REASON}`);
  }

  return (
    <AuthProvider initialUser={initialUser}>
      <div className="min-h-screen flex flex-col bg-background">
        <SkipLink />
        <DashboardNavbar />
        {/* Skip-link target; programmatic focus only, so no ring around the page. */}
        <main id="main" tabIndex={-1} className="flex-1 w-full bg-background transition-colors duration-200 focus:outline-none">
          {children}
        </main>
      </div>
    </AuthProvider>
  );
}
