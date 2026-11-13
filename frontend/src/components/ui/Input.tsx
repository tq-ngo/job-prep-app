"use client";

import { useId, useState, type ComponentProps, type ReactNode } from "react";
import { ChevronDown, Eye, EyeOff } from "lucide-react";
import { cn } from "./cn";
import { useFieldControl } from "./Field";

export type ControlSize = "sm" | "md";

// border-strong (3:1) because the border is what identifies the control;
// the decorative slate-soft border failed WCAG 1.4.11. Focus uses the global
// :focus-visible ring, pulled in tight so it hugs the border.
const control =
  "w-full bg-background border border-border-strong rounded-control text-slate-ink font-sans " +
  "placeholder:text-foreground-subtle transition-all duration-150 focus-visible:outline-offset-0 " +
  "hover:border-slate-ink/50 focus:bg-background " +
  "aria-invalid:border-amber-clay disabled:cursor-not-allowed disabled:bg-neutral-soft disabled:text-foreground-subtle";

const sizes: Record<ControlSize, string> = {
  sm: "h-8 px-3 text-xs",
  md: "h-11 px-4 text-sm",
};

type InputProps = Omit<ComponentProps<"input">, "size"> & {
  size?: ControlSize;
  /** Decorative icon inside the left edge (e.g. a search glass). */
  leadingIcon?: ReactNode;
  /** Pill shape for M3 search bars. */
  pill?: boolean;
};

/** Text input. Inside a <Field> it picks up its id, label and descriptions. */
export function Input({ size = "md", leadingIcon, pill, className, ...props }: InputProps) {
  const field = useFieldControl();
  const input = (
    <input
      {...field}
      {...props}
      className={cn(
        control,
        sizes[size],
        pill && "rounded-full",
        leadingIcon ? (size === "sm" ? "pl-8" : "pl-10") : undefined,
        !leadingIcon && className,
      )}
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

/**
 * Password input with a show/hide toggle, so people can check what they
 * typed (especially on phones). The toggle is a real button, outside the
 * input's label, announced as pressed when the password is visible.
 */
export function PasswordInput({ size = "md", className, ...props }: Omit<InputProps, "type" | "leadingIcon">) {
  const [visible, setVisible] = useState(false);
  const field = useFieldControl();
  const fallbackId = useId();
  const inputId = props.id ?? field?.id ?? fallbackId;
  return (
    <div className={cn("relative", className)}>
      <Input {...props} id={inputId} size={size} type={visible ? "text" : "password"} className={size === "sm" ? "pr-9" : "pr-12"} />
      <button
        type="button"
        aria-label="Show password"
        aria-pressed={visible}
        aria-controls={inputId}
        onClick={() => setVisible((v) => !v)}
        className={cn(
          "absolute top-1/2 -translate-y-1/2 flex items-center justify-center rounded-control text-foreground-subtle hover:text-slate-ink",
          size === "sm" ? "right-1 h-6 w-7" : "right-1.5 h-8 w-9",
        )}
      >
        {visible ? <EyeOff size={16} aria-hidden="true" /> : <Eye size={16} aria-hidden="true" />}
      </button>
    </div>
  );
}
