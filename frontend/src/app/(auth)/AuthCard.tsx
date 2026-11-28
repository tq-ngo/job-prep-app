import type { ReactNode } from "react";

interface AuthCardProps {
  title: string;
  subtitle: string;
  footer: ReactNode;
  children: ReactNode;
}

/** Shared card frame for /login and /register. */
export default function AuthCard({ title, subtitle, footer, children }: AuthCardProps) {
  return (
    <div className="w-full max-w-md rounded-xl bg-surface-container-lowest border border-outline-variant shadow-level-1 dark:shadow-none p-6 sm:p-8">
      <div className="text-center mb-6">
        <h1 className="text-headline-small font-semibold text-on-surface">{title}</h1>
        <p className="text-body-medium text-on-surface-variant mt-1.5">{subtitle}</p>
      </div>
      {children}
      <div className="mt-6 pt-5 border-t border-outline-variant text-center text-body-small text-on-surface-variant">
        {footer}
      </div>
    </div>
  );
}
