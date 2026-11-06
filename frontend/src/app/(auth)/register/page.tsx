import { safeNextPath } from "@/lib/urls";
import RegisterForm from "./RegisterForm";

/**
 * Server component (like /login) so the form is in the initial HTML and
 * `next` survives the trip through registration and sign-in. It used to be
 * dropped, so signing up from a deep link always landed on /jobs.
 */
export default async function RegisterPage({ searchParams }: { searchParams: Promise<{ next?: string }> }) {
  const { next } = await searchParams;
  return <RegisterForm nextPath={safeNextPath(next)} />;
}
