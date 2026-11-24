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

const assistStyles = "bg-primary-container text-on-primary-container border border-primary/25";
const suggestionStyles = "bg-secondary-container text-on-secondary-container border border-outline-variant";
const neutralStyles = "bg-surface-container-low text-on-surface border border-outline-variant";
const warningStyles = "bg-error-container text-on-error-container border border-error/25";

// Every text/surface combination here is verified in scripts/contrast-pairs.mjs.
const variants: Record<BadgeVariant, string> = {
  // M3 Suggestion / Status chips (source, remote)
  source: suggestionStyles,
  remote: suggestionStyles,
  suggestion: suggestionStyles,
  // M3 Assist chips (extracted skills)
  skill: assistStyles,
  assist: assistStyles,
  // M3 Filter chips (sponsorship)
  sponsorship: assistStyles,
  filter: assistStyles,
  // Restriction / warning chips
  citizenship: warningStyles,
  no_sponsorship: warningStyles,
  // Neutral M3 chip
  neutral: neutralStyles,
};

type BadgeProps = ComponentProps<"span"> & {
  variant?: BadgeVariant;
  /** `md` for standalone tag lists; `sm` inline next to text. */
  size?: "sm" | "md";
};

/** M3 Pill Chip / Badge: assist, filter, suggestion, status, and tag chips. */
export default function Badge({ variant = "neutral", size = "sm", className, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full font-mono uppercase tracking-wider shrink-0 select-none",
        size === "sm" ? "px-2.5 py-0.5 text-label-small" : "px-3 py-1 text-label-medium",
        variants[variant],
        className,
      )}
      {...props}
    />
  );
}
