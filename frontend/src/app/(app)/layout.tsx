import { cookies } from "next/headers";
import DashboardNavbar from "@/components/DashboardNavbar";
import { AuthProvider } from "@/context/AuthContext";
import type { User } from "@/lib/api";

/**
 * Resolve the signed-in user on the server so the first paint is correct.
 *
 * proxy.ts has already verified the access token's signature before this
 * renders. This call is the authoritative check against the API (revocation,
 * disabled accounts); undefined means "unknown" and the client retries.
 */
async function getInitialUser(): Promise<User | null | undefined> {
  const apiUrl = process.env.INTERNAL_API_URL || "http://localhost:8000";
  const cookieHeader = (await cookies()).toString();
  if (!cookieHeader) return null;
  try {
    const res = await fetch(`${apiUrl}/api/v1/auth/me`, {
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
  return (
    <AuthProvider initialUser={initialUser}>
      <div className="min-h-screen flex flex-col bg-background">
        <DashboardNavbar />
        <main className="flex-1 w-full bg-background transition-colors duration-200">
          {children}
        </main>
      </div>
    </AuthProvider>
  );
}
