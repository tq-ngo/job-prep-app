import LoginForm from "./LoginForm";

/**
 * Server component so the form is present in the initial HTML.
 *
 * `next` is read from searchParams here rather than with useSearchParams in
 * the client component: that forced the whole form into a Suspense boundary
 * that rendered `null` on the server, leaving the login page an empty shell
 * in the HTML (no form, no Google button) until JS hydrated.
 */
export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string }>;
}) {
  const { next } = await searchParams;
  // Only accept relative paths — an absolute URL here would be an open redirect.
  // Backslashes too: browsers treat `/\evil.com` as `//evil.com`.
  const nextPath =
    next && next.startsWith("/") && !next.startsWith("//") && !next.includes("\\")
      ? next
      : "/jobs";
  return <LoginForm nextPath={nextPath} />;
}
