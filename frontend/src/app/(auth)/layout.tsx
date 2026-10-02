/**
 * Auth routes render as a plain server layout.
 *
 * This used to wrap children in <AuthGuard>, whose `isLoading` state starts
 * true — so the server rendered a loading spinner instead of the sign-in
 * form, and the real page only appeared after hydration and a round trip to
 * /auth/me. Redirects are now handled at the edge by src/proxy.ts, which runs
 * before any rendering, so the guard is both redundant and harmful here.
 */
export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
