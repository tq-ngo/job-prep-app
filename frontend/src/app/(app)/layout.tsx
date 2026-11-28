import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";
import DashboardNavbar from "@/components/DashboardNavbar";
import SkipLink from "@/components/SkipLink";
import { AuthProvider } from "@/context/AuthContext";
import type { User } from "@/lib/api";
import { PATHNAME_HEADER, SESSION_INVALID_REASON } from "@/proxy";
import { INTERNAL_API_URL } from "@/lib/server-api";
import { safeNextPath } from "@/lib/urls";

type SessionResolution =
  | { status: "authenticated"; user: User }
  | { status: "unauthenticated" }
  | { status: "unavailable" };

/**
 * Authoritative server-side session verification against `/api/v1/auth/me`.
 *
 * Fails CLOSED on 5xx / 429 / network outages instead of rendering protected
 * `{children}`, so a revoked or disabled session can never bypass this check
 * during a backend hiccup.
 */
async function resolveInitialSession(): Promise<SessionResolution> {
  const cookieStore = await cookies();
  const cookieHeader = cookieStore.toString();
  if (!cookieHeader) return { status: "unauthenticated" };
  try {
    const res = await fetch(`${INTERNAL_API_URL}/api/v1/auth/me`, {
      headers: { cookie: cookieHeader },
      cache: "no-store",
    });
    if (res.status === 401 || res.status === 403) {
      return { status: "unauthenticated" };
    }
    if (!res.ok) {
      return { status: "unavailable" };
    }
    const user = (await res.json()) as User;
    return { status: "authenticated", user };
  } catch {
    return { status: "unavailable" };
  }
}

export default async function ProtectedLayout({ children }: { children: React.ReactNode }) {
  const session = await resolveInitialSession();

  if (session.status === "unauthenticated") {
    const [headerList, cookieStore] = await Promise.all([headers(), cookies()]);
    const pathname = safeNextPath(headerList.get(PATHNAME_HEADER), "/jobs");
    const hasRefreshHint = typeof cookieStore.has === "function"
      ? cookieStore.has("csrf_token") && !cookieStore.has("auth_resume_attempt")
      : false;
    if (hasRefreshHint) {
      redirect(`/api/v1/auth/resume?next=${encodeURIComponent(pathname)}`);
    }
    redirect(`/login?next=${encodeURIComponent(pathname)}&reason=${SESSION_INVALID_REASON}`);
  }

  if (session.status === "unavailable") {
    const headerList = await headers();
    const pathname = safeNextPath(headerList.get(PATHNAME_HEADER), "/jobs");
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-surface text-on-surface px-4">
        <main
          id="main"
          role="main"
          className="w-full max-w-md rounded-md bg-surface-container-low border border-outline-variant p-6 text-center"
        >
          <h1 className="text-title-large font-sans font-medium text-on-surface">
            Service temporarily unavailable
          </h1>
          <p className="mt-2 text-body-medium text-on-surface-variant">
            We couldn&apos;t verify your session right now. Please try again in a moment.
          </p>
          <div className="mt-5 flex items-center justify-center gap-3">
            <a
              href={pathname}
              className="inline-flex h-10 items-center justify-center rounded-full bg-primary px-5 text-label-large font-medium text-on-primary"
            >
              Retry
            </a>
            <a
              href="/login"
              className="inline-flex h-10 items-center justify-center rounded-full border border-outline px-5 text-label-large font-medium text-on-surface"
            >
              Sign in
            </a>
          </div>
        </main>
      </div>
    );
  }

  return (
    <AuthProvider initialUser={session.user}>
      <div className="min-h-screen flex flex-col bg-surface">
        <SkipLink />
        <DashboardNavbar />
        <main id="main" tabIndex={-1} className="flex-1 w-full bg-surface transition-colors duration-200 focus:outline-none">
          {children}
        </main>
      </div>
    </AuthProvider>
  );
}
