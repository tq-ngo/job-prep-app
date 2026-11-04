import LoginForm from "./LoginForm";

/**
 * Server component so the form is present in the initial HTML.
 *
 * `next` is read from searchParams here rather than with useSearchParams in
 * the client component: that forced the whole form into a Suspense boundary
 * that rendered `null` on the server, leaving the login page an empty shell
 * in the HTML (no form, no Google button) until JS hydrated.
 */
// Reasons the backend's Google callback sends users back here with.
// Unknown codes show nothing rather than echoing attacker-chosen text.
const ERROR_MESSAGES: Record<string, string> = {
  account_exists:
    "An account with this email already exists. Sign in with your email and password instead.",
  account_disabled: "This account has been disabled.",
  oauth_failed: "Google sign-in couldn't be completed. Please try again.",
  access_denied: "Google sign-in was cancelled.",
};

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string; error?: string }>;
}) {
  const { next, error } = await searchParams;
  // Only accept relative paths — an absolute URL here would be an open redirect.
  // Backslashes too: browsers treat `/\evil.com` as `//evil.com`.
  const nextPath =
    next && next.startsWith("/") && !next.startsWith("//") && !next.includes("\\")
      ? next
      : "/jobs";
  const initialError = (error && ERROR_MESSAGES[error]) || "";
  return <LoginForm nextPath={nextPath} initialError={initialError} />;
}
