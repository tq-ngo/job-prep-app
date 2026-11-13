import type { ReactNode } from "react";
import Card from "@/components/ui/Card";

/** Centered card shell shared by the sign-in and registration pages. */
export default function AuthCard({
  title,
  subtitle,
  footer,
  children,
}: {
  title: string;
  subtitle: string;
  footer: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4 font-sans">
      <Card tone="elevated" padding="lg" className="w-full max-w-sm shadow-pop border border-slate-soft/80">
        <h1 className="text-2xl font-serif font-medium text-slate-ink mb-2 text-center">{title}</h1>
        <p className="text-foreground-muted text-center mb-8 text-sm">{subtitle}</p>
        {children}
        <p className="mt-6 text-center text-sm text-foreground-muted">{footer}</p>
      </Card>
    </div>
  );
}
