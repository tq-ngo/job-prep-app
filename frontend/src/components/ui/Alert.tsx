import type { ReactNode } from "react";
import { cn } from "./cn";

export type AlertVariant = "error" | "info";

const variants: Record<AlertVariant, string> = {
  error: "bg-amber-clay/10 border-amber-clay/30 text-amber-clay-on-tint",
  info: "bg-spruce-green/10 border-spruce-green/30 text-spruce-green",
};

interface AlertProps {
  variant?: AlertVariant;
  /** Leading icon (decorative). */
  icon?: ReactNode;
  /** Trailing control, e.g. a Retry button. */
  action?: ReactNode;
  className?: string;
  children: ReactNode;
}

/**
 * Inline message banner. Errors use role="alert" (announced immediately);
 * info uses role="status" (announced politely, without interrupting).
 * Render it conditionally: the role announces content as it appears.
 */
export default function Alert({ variant = "info", icon, action, className, children }: AlertProps) {
  return (
    <div
      role={variant === "error" ? "alert" : "status"}
      className={cn("flex items-center gap-2 rounded-control border px-4 py-3 text-sm", variants[variant], className)}
    >
      {icon && (
        <span aria-hidden="true" className="shrink-0">
          {icon}
        </span>
      )}
      <div className="min-w-0 flex-1">{children}</div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}
