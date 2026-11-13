import type { ComponentProps } from "react";
import { cn } from "./cn";

export type BadgeVariant = "source" | "remote" | "skill" | "neutral";

// Every text/surface combination here is in scripts/contrast-pairs.mjs.
const variants: Record<BadgeVariant, string> = {
  // Where a listing came from (github, linkedin) - M3 status chip
  source: "bg-amber-clay/10 text-amber-clay-on-tint border border-amber-clay/20",
  remote: "bg-amber-clay/10 text-amber-clay-on-tint border border-amber-clay/20",
  // Extracted skill - M3 assist chip
  skill: "bg-spruce-green/10 text-spruce-green border border-spruce-green/25",
  // Neutral tag / filter
  neutral: "bg-neutral-soft text-slate-ink border border-slate-soft",
};

type BadgeProps = ComponentProps<"span"> & {
  variant?: BadgeVariant;
  /** `md` for standalone tag lists; `sm` inline next to text. */
  size?: "sm" | "md";
};

/** M3 Pill Chip / Badge: sources, skills, tags, statuses. */
export default function Badge({ variant = "neutral", size = "sm", className, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full font-mono uppercase tracking-wider shrink-0 select-none",
        size === "sm" ? "px-2 py-0.5 text-2xs" : "px-3 py-1 text-xs",
        variants[variant],
        className,
      )}
      {...props}
    />
  );
}
