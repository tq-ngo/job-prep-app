"use client";

import { useId, useState, type ComponentProps, type ReactNode } from "react";
import { ChevronDown, Eye, EyeOff } from "lucide-react";
import { cn } from "./cn";
import { useFieldControl } from "./Field";

export type ControlSize = "sm" | "md";

// outline (>= 3:1) identifies the control boundary per WCAG 1.4.11.
// Focus uses the global :focus-visible ring, pulled in tight to hug the border.
const control =
  "w-full bg-surface-container-lowest dark:bg-surface-container-low border border-outline rounded-sm text-on-surface font-sans " +
  "placeholder:text-on-surface-variant transition-[background-color,border-color,color] duration-150 focus-visible:outline-offset-0 " +
  "hover:border-on-surface focus:bg-surface-container-lowest dark:focus:bg-surface-container-default focus:border-primary " +
  "aria-invalid:border-error disabled:cursor-not-allowed disabled:bg-surface-container-default disabled:text-on-surface-variant";

const sizes: Record<ControlSize, string> = {
  sm: "h-8 px-3 text-body-small",
  md: "h-10 px-4 text-body-medium",
};

type InputProps = Omit<ComponentProps<"input">, "size"> & {
  size?: ControlSize;
  /** Decorative icon inside the left edge (e.g. a search glass). */
  leadingIcon?: ReactNode;
  /** Pill shape when explicitly requested; default is Hybrid `rounded-sm`. */
  pill?: boolean;
  /** Classes applied directly to the `<input>` element (always works, even with `leadingIcon`). */
  inputClassName?: string;
};

/** Text input. Inside a <Field> it picks up its id, label and descriptions. */
export function Input({ size = "md", leadingIcon, pill, className, inputClassName, ...props }: InputProps) {
  const field = useFieldControl();
  const fallbackId = useId();
  const inputId = props.id ?? field?.id ?? fallbackId;
  const input = (
    <input
      {...field}
      {...props}
      id={inputId}
      className={cn(
        control,
        sizes[size],
        pill && "rounded-full",
        leadingIcon ? (size === "sm" ? "pl-8" : "pl-10") : undefined,
        !leadingIcon && className,
        inputClassName,
      )}
    />
  );
  if (!leadingIcon) return input;
  return (
    <div className={cn("relative", className)}>
      <span
        aria-hidden="true"
        className={cn(
          "pointer-events-none absolute top-1/2 -translate-y-1/2 text-on-surface-variant",
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
        size={size === "sm" ? 14 : 16}
        strokeWidth={1.5}
        aria-hidden="true"
        className={cn(
          "pointer-events-none absolute top-1/2 -translate-y-1/2 text-on-surface-variant",
          size === "sm" ? "right-2" : "right-3.5",
        )}
      />
    </div>
  );
}

/** Multi-line text input. */
export function Textarea({ className, ...props }: ComponentProps<"textarea">) {
  const field = useFieldControl();
  return <textarea {...field} {...props} className={cn(control, "px-4 py-3 text-body-medium min-h-24", className)} />;
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
          "absolute top-1/2 -translate-y-1/2 flex items-center justify-center rounded-sm text-on-surface-variant hover:text-on-surface hover:bg-on-surface/8 focus-visible:bg-on-surface/12 transition-colors cursor-pointer",
          size === "sm" ? "right-1 h-6 w-6" : "right-1.5 h-8 w-8",
        )}
      >
        {visible ? <EyeOff size={16} strokeWidth={1.5} aria-hidden="true" /> : <Eye size={16} strokeWidth={1.5} aria-hidden="true" />}
      </button>
    </div>
  );
}
