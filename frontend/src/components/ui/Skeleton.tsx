import type { CSSProperties, ReactNode } from "react";
import { cn } from "./cn";

/** A pulsing placeholder block. Hidden from screen readers; see SkeletonGroup. */
export default function Skeleton({ className, style }: { className?: string; style?: CSSProperties }) {
  return <div aria-hidden="true" style={style} className={cn("animate-pulse rounded-control bg-slate-soft", className)} />;
}

/**
 * Wraps skeletons so assistive tech hears one "Loading…" message instead of
 * nothing (the blocks themselves are aria-hidden).
 */
export function SkeletonGroup({ label, className, children }: { label: string; className?: string; children: ReactNode }) {
  return (
    <div role="status" className={className}>
      <span className="sr-only">{label}</span>
      {children}
    </div>
  );
}
