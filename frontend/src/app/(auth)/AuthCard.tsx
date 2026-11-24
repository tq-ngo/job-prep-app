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
    <div className="min-h-screen flex items-center justify-center bg-surface px-4 font-sans">
      <Card tone="elevated" padding="lg" className="w-full max-w-sm rounded-lg shadow-level-2">
        <h1 className="text-headline-small font-serif font-medium text-on-surface mb-2 text-center">{title}</h1>
        <p className="text-on-surface-variant text-center mb-8 text-body-medium">{subtitle}</p>
        {children}
        <p className="mt-6 text-center text-body-medium text-on-surface-variant">{footer}</p>
      </Card>
    </div>
  );
}
