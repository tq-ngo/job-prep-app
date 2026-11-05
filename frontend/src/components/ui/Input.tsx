"use client";

import type { ComponentProps, ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "./cn";
import { useFieldControl } from "./Field";

export type ControlSize = "sm" | "md";

// border-strong (3:1) because the border is what identifies the control;
// the decorative slate-soft border failed WCAG 1.4.11. Focus uses the global
// :focus-visible ring, pulled in tight so it hugs the border.
const control =
  "w-full bg-background border border-border-strong rounded-control text-slate-ink font-sans " +
  "placeholder:text-foreground-subtle transition-colors focus-visible:outline-offset-0 " +
  "aria-invalid:border-amber-clay disabled:cursor-not-allowed disabled:bg-neutral-soft disabled:text-foreground-subtle";

const sizes: Record<ControlSize, string> = {
  sm: "h-8 px-2.5 text-xs",
  md: "h-11 px-4 text-sm",
};

type InputProps = Omit<ComponentProps<"input">, "size"> & {
  size?: ControlSize;
  /** Decorative icon inside the left edge (e.g. a search glass). */
  leadingIcon?: ReactNode;
};

/** Text input. Inside a <Field> it picks up its id, label and descriptions. */
export function Input({ size = "md", leadingIcon, className, ...props }: InputProps) {
  const field = useFieldControl();
  const input = (
    <input
      {...field}
      {...props}
      className={cn(control, sizes[size], leadingIcon ? (size === "sm" ? "pl-8" : "pl-10") : undefined, !leadingIcon && className)}
    />
  );
  if (!leadingIcon) return input;
  return (
    <div className={cn("relative", className)}>
      <span
        aria-hidden="true"
        className={cn(
          "pointer-events-none absolute top-1/2 -translate-y-1/2 text-foreground-subtle",
          size === "sm" ? "left-2.5" : "left-3.5",
        )}
      >
        {leadingIcon}
      </span>
      {input}
    </div>
  );
}

type SelectProps = Omit<ComponentProps<"select">, "size"> & { size?: ControlSize };

/** Native select with a consistent chevron (appearance-none drops the OS one). */
export function Select({ size = "md", className, children, ...props }: SelectProps) {
  const field = useFieldControl();
  return (
    <div className={cn("relative", className)}>
      <select
        {...field}
        {...props}
        className={cn(control, sizes[size], "appearance-none cursor-pointer", size === "sm" ? "pr-7" : "pr-10")}
      >
        {children}
      </select>
      <ChevronDown
        size={size === "sm" ? 13 : 16}
        aria-hidden="true"
        className={cn(
          "pointer-events-none absolute top-1/2 -translate-y-1/2 text-foreground-subtle",
          size === "sm" ? "right-2" : "right-3.5",
        )}
      />
    </div>
  );
}

/** Multi-line text input. */
export function Textarea({ className, ...props }: ComponentProps<"textarea">) {
  const field = useFieldControl();
  return <textarea {...field} {...props} className={cn(control, "px-4 py-3 text-sm min-h-24", className)} />;
}
