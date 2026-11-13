import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";
import { cn } from "./cn";
import Spinner from "./Spinner";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
export type ButtonSize = "xs" | "sm" | "md" | "lg" | "icon";

const base =
  "inline-flex items-center justify-center font-sans font-medium rounded-control whitespace-nowrap " +
  "transition-all duration-150 cursor-pointer disabled:cursor-not-allowed aria-disabled:cursor-not-allowed select-none " +
  "active:scale-[0.98] disabled:active:scale-100";

const variants: Record<ButtonVariant, string> = {
  // M3 Filled Button: high-emphasis solid container with subtle elevation
  primary:
    "bg-spruce-green text-warm-ivory shadow-card hover:bg-spruce-green-hover hover:shadow-m3-1 " +
    "disabled:bg-slate-soft disabled:text-foreground-subtle disabled:shadow-none",
  // M3 Filled Tonal Button: medium-emphasis tonal surface container
  secondary:
    "bg-neutral-soft border border-slate-soft text-slate-ink hover:bg-surface-container hover:border-spruce-green/40 " +
    "aria-pressed:bg-spruce-green/10 aria-pressed:border-spruce-green/40 aria-pressed:text-spruce-green " +
    "disabled:text-foreground-subtle disabled:hover:border-slate-soft disabled:hover:bg-neutral-soft",
  // M3 Text / Ghost Button: low-emphasis flat interaction
  ghost:
    "text-foreground-muted hover:text-slate-ink hover:bg-neutral-soft active:bg-surface-container " +
    "disabled:text-foreground-subtle disabled:hover:bg-transparent",
  // M3 Danger Tonal Button
  danger:
    "bg-amber-clay/10 border border-amber-clay/30 text-amber-clay-on-tint hover:bg-amber-clay/15 hover:border-amber-clay " +
    "disabled:opacity-60",
};

const sizes: Record<ButtonSize, string> = {
  xs: "h-6 px-2 gap-1 text-2xs",
  sm: "h-8 px-3 gap-1.5 text-xs",
  md: "h-10 px-4 gap-2 text-sm",
  lg: "h-11 px-6 gap-2.5 text-sm",
  icon: "h-8 w-8 shrink-0",
};

interface StyleProps {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Stretch to the container's width. */
  block?: boolean;
  className?: string;
}

/** The class string, for the rare element that can't be a Button/ButtonLink. */
export function buttonClasses({ variant = "primary", size = "md", block, className }: StyleProps = {}) {
  return cn(base, variants[variant], sizes[size], block && "w-full", className);
}

type ButtonProps = ComponentProps<"button"> &
  StyleProps & {
    /** Leading icon; replaced by a spinner while `loading`. */
    icon?: ReactNode;
    /** Disables the button and marks it busy. Change the label to say what's happening. */
    loading?: boolean;
  };

export function Button({
  variant,
  size,
  block,
  className,
  icon,
  loading = false,
  disabled,
  type = "button",
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={buttonClasses({ variant, size, block, className })}
      {...props}
    >
      {loading ? <Spinner size={size === "xs" ? 11 : 14} /> : icon}
      {children}
    </button>
  );
}

type ButtonLinkProps = Omit<ComponentProps<"a">, "href"> &
  StyleProps & {
    href: string;
    icon?: ReactNode;
    /** Passed to next/link; ignored for `external` and `native` links. */
    prefetch?: boolean;
    /** Opens in a new tab (off-site links such as apply URLs). */
    external?: boolean;
    /**
     * A plain <a> with a full page load instead of client-side routing. Needed
     * for API routes such as the Google sign-in redirect, which Next's router
     * would otherwise try to fetch as a page.
     */
    native?: boolean;
  };

/** A link styled as a button. Use for navigation; use Button for actions. */
export function ButtonLink({
  variant,
  size,
  block,
  className,
  icon,
  external = false,
  native = false,
  href,
  prefetch,
  children,
  ...props
}: ButtonLinkProps) {
  const classes = buttonClasses({ variant, size, block, className });
  if (external || native) {
    return (
      <a
        href={href}
        className={classes}
        {...(external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
        {...props}
      >
        {icon}
        {children}
      </a>
    );
  }
  return (
    <Link href={href} prefetch={prefetch} className={classes} {...props}>
      {icon}
      {children}
    </Link>
  );
}
