import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";
import { cn } from "./cn";
import Spinner from "./Spinner";

export type ButtonVariant =
  | "primary"
  | "secondary"
  | "ghost"
  | "danger"
  | "filled"
  | "tonal"
  | "outlined"
  | "text";
export type ButtonSize = "xs" | "sm" | "md" | "lg" | "icon";

const base =
  "inline-flex items-center justify-center font-sans font-medium rounded-full whitespace-nowrap " +
  "transition-[background-color,border-color,color,box-shadow,transform] duration-150 cursor-pointer " +
  "disabled:cursor-not-allowed aria-disabled:cursor-not-allowed select-none " +
  "active:scale-[0.98] disabled:active:scale-100 motion-reduce:active:scale-100";

const filledStyles =
  "bg-primary text-on-primary shadow-level-1 dark:shadow-none hover:bg-primary-hover hover:shadow-level-2 dark:hover:shadow-none " +
  "focus-visible:bg-primary-hover active:bg-primary-hover " +
  "disabled:bg-surface-container-highest disabled:text-on-surface-variant disabled:shadow-none";

const tonalStyles =
  "bg-secondary-container text-on-secondary-container hover:shadow-level-1 dark:hover:shadow-none hover:bg-primary-container hover:text-on-primary-container " +
  "focus-visible:bg-primary-container focus-visible:text-on-primary-container active:bg-primary-container " +
  "aria-pressed:bg-primary-container aria-pressed:text-on-primary-container " +
  "disabled:bg-surface-container-highest disabled:text-on-surface-variant disabled:shadow-none";

const outlinedStyles =
  "bg-surface border border-outline text-on-surface hover:bg-on-surface/8 hover:border-primary " +
  "focus-visible:bg-on-surface/12 active:bg-on-surface/12 " +
  "aria-pressed:bg-primary-container aria-pressed:border-primary aria-pressed:text-on-primary-container " +
  "disabled:border-outline-variant disabled:text-on-surface-variant disabled:bg-surface";

const textStyles =
  "text-on-surface-variant hover:text-on-surface hover:bg-on-surface/8 " +
  "focus-visible:text-on-surface focus-visible:bg-on-surface/12 active:bg-on-surface/12 " +
  "disabled:text-on-surface-variant disabled:hover:bg-transparent";

const variants: Record<ButtonVariant, string> = {
  primary: filledStyles,
  filled: filledStyles,
  tonal: tonalStyles,
  secondary: outlinedStyles,
  outlined: outlinedStyles,
  ghost: textStyles,
  text: textStyles,
  danger:
    "bg-error-container text-on-error-container border border-error/30 hover:bg-error hover:text-on-error " +
    "focus-visible:bg-error focus-visible:text-on-error active:bg-error active:text-on-error " +
    "disabled:bg-surface-container-highest disabled:text-on-surface-variant disabled:border-outline-variant",
};

const sizes: Record<ButtonSize, string> = {
  xs: "h-6 px-2.5 gap-1 text-label-small",
  sm: "h-8 px-3.5 gap-1.5 text-label-medium",
  md: "h-10 px-5 gap-2 text-label-large",
  lg: "h-12 px-6 gap-2 text-label-large",
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
      {loading ? <Spinner size={size === "xs" ? 12 : 14} /> : icon}
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
