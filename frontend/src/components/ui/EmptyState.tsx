import type { ReactNode } from "react";
import { cn } from "./cn";

interface EmptyStateProps {
  icon?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  /** Usually a Button that clears filters or starts a fetch. */
  action?: ReactNode;
  /** Heading level for the title, to fit the page outline. */
  headingLevel?: 2 | 3;
  className?: string;
}

/** Centered "nothing here" message with an optional way forward. */
export default function EmptyState({ icon, title, description, action, headingLevel = 2, className }: EmptyStateProps) {
  const Heading = headingLevel === 2 ? "h2" : "h3";
  return (
    <div className={cn("flex flex-col items-center justify-center py-24 text-center", className)}>
      {icon && (
        <div
          aria-hidden="true"
          className="w-14 h-14 rounded-full bg-spruce-green/10 text-spruce-green border border-spruce-green/20 flex items-center justify-center mb-4 shadow-sm"
        >
          {icon}
        </div>
      )}
      <Heading className="text-lg font-serif text-slate-ink mb-1.5">{title}</Heading>
      {description && <p className="text-foreground-muted max-w-sm font-sans text-xs leading-relaxed">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
