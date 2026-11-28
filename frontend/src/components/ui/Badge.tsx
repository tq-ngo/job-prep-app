import type { ComponentProps } from "react";
import { cn } from "./cn";

export type BadgeVariant =
  | "source"
  | "remote"
  | "skill"
  | "neutral"
  | "sponsorship"
  | "citizenship"
  | "no_sponsorship"
  | "assist"
  | "filter"
  | "suggestion";

const neutralStyles = "bg-surface-container-low text-on-surface border border-outline-variant";
const activeStyles = "bg-primary-container text-on-primary-container border border-primary/25";
const warningStyles = "bg-error-container text-on-error-container border border-error/25";

// Every text/surface combination here is verified in scripts/contrast-pairs.mjs.
// Keep routine metadata tags (skills, source, remote) calm and neutral so
// semantic tints (sponsorship, active filters, warnings) carry real signal.
const variants: Record<BadgeVariant, string> = {
  source: neutralStyles,
  remote: neutralStyles,
  suggestion: neutralStyles,
  skill: neutralStyles,
  neutral: neutralStyles,
  assist: activeStyles,
  sponsorship: activeStyles,
  filter: activeStyles,
  citizenship: warningStyles,
  no_sponsorship: warningStyles,
};

type BadgeProps = ComponentProps<"span"> & {
  variant?: BadgeVariant;
  /** `md` for standalone tag lists; `sm` inline next to text. */
  size?: "sm" | "md";
};

/** Compact metadata tag / chip (Hybrid M3 + unslop `rounded-xs`). */
export default function Badge({ variant = "neutral", size = "sm", className, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-xs font-mono font-medium shrink-0 select-none",
        size === "sm" ? "px-2 py-0.5 text-label-small" : "px-2.5 py-1 text-label-medium",
        variants[variant],
        className,
      )}
      {...props}
    />
  );
}
