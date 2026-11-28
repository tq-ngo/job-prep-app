import Link from "next/link";
import SkipLink from "@/components/SkipLink";
import ThemeToggle from "@/components/ThemeToggle";
import { AuthProvider } from "@/context/AuthContext";

/**
 * Auth routes (`/login`, `/register`) need `AuthProvider` so `LoginForm` can
 * invoke `completeLogin()` after setting HttpOnly cookies. Keep them out of
 * `(marketing)` so the public landing page stays 100% cacheable without auth.
 */
export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider initialUser={null}>
      <div className="min-h-screen flex flex-col bg-surface text-on-surface">
        <SkipLink />
        <header className="max-w-app w-full mx-auto h-14 px-4 sm:px-6 flex items-center justify-between">
          <Link
            href="/"
            className="text-title-large font-semibold tracking-tight text-on-surface hover:text-primary transition-colors"
          >
            JobPrep
          </Link>
          <ThemeToggle />
        </header>
        <main id="main" tabIndex={-1} className="flex-1 flex items-center justify-center px-4 py-8 focus:outline-none">
          {children}
        </main>
      </div>
    </AuthProvider>
  );
}
