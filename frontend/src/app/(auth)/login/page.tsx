import { safeNextPath } from "@/lib/urls";
import { SESSION_INVALID_REASON } from "@/proxy";
import LoginForm from "./LoginForm";

/**
 * Server component so the form is present in the initial HTML.
 *
 * Query parameters are read here rather than with useSearchParams in the
 * client component: that forced the whole form into a Suspense boundary
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
  searchParams: Promise<{ next?: string; error?: string; registered?: string; reason?: string }>;
}) {
  const { next, error, registered, reason } = await searchParams;
  const initialError = (error && ERROR_MESSAGES[error]) || "";
  const notice =
    registered === "1"
      ? "Account created. Sign in to continue."
      : reason === SESSION_INVALID_REASON
        ? "Your session has ended. Please sign in again."
        : "";
  return <LoginForm nextPath={safeNextPath(next)} initialError={initialError} notice={notice} />;
}
