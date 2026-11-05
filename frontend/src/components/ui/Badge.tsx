import type { ComponentProps } from "react";
import { cn } from "./cn";

export type BadgeVariant = "source" | "remote" | "skill" | "neutral";

// Every text/surface combination here is in scripts/contrast-pairs.mjs.
const variants: Record<BadgeVariant, string> = {
  // Where a listing came from (github, linkedin).
  source: "bg-amber-clay/10 text-amber-clay-on-tint",
  remote: "bg-amber-clay/10 text-amber-clay-on-tint",
  skill: "bg-spruce-green/10 text-spruce-green border border-spruce-green/20",
  neutral: "bg-neutral-soft text-slate-ink border border-slate-soft",
};

type BadgeProps = ComponentProps<"span"> & {
  variant?: BadgeVariant;
  /** `md` for standalone tag lists; `sm` inline next to text. */
  size?: "sm" | "md";
};

/** Small mono label: sources, skills, tags, statuses. */
export default function Badge({ variant = "neutral", size = "sm", className, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-control font-mono uppercase tracking-wider shrink-0",
        size === "sm" ? "px-1.5 py-0.5 text-2xs" : "px-2.5 py-1 text-xs",
        variants[variant],
        className,
      )}
      {...props}
    />
  );
}
