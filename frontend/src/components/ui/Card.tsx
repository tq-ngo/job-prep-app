import type { HTMLAttributes } from "react";
import { cn } from "./cn";

export type CardTone = "default" | "muted" | "elevated" | "outlined" | "filled";
export type CardPadding = "none" | "sm" | "md" | "lg";

const outlinedStyles = "bg-surface border border-outline-variant";
const filledStyles = "bg-surface-container-low";
const elevatedStyles =
  "bg-surface-container-lowest dark:bg-surface-container-default shadow-level-1 dark:shadow-none dark:border dark:border-outline-variant";

const tones: Record<CardTone, string> = {
  default: outlinedStyles,
  outlined: outlinedStyles,
  muted: filledStyles,
  filled: filledStyles,
  elevated: elevatedStyles,
};

const paddings: Record<CardPadding, string> = {
  none: "",
  sm: "p-4",
  md: "p-6",
  lg: "p-8",
};

interface CardStyle {
  tone?: CardTone;
  /** Alias for `tone` for ergonomic call sites. */
  variant?: CardTone;
  padding?: CardPadding;
  /** Hover affordance, for cards that are links or buttons. */
  interactive?: boolean;
  className?: string;
}

/** The class string, for a card that has to be another element (e.g. an <a>). */
export function cardClasses({ tone, variant, padding = "md", interactive, className }: CardStyle = {}) {
  const resolvedTone = variant ?? tone ?? "default";
  return cn(
    "rounded-lg",
    tones[resolvedTone],
    paddings[padding],
    interactive &&
      "transition-[background-color,border-color,box-shadow] duration-150 hover:bg-surface-container-low hover:shadow-level-2 dark:hover:shadow-none dark:hover:border-outline",
    className,
  );
}

type CardProps = HTMLAttributes<HTMLElement> & CardStyle & { as?: "div" | "section" | "article" | "li" };

/** Surface container for grouped content. */
export default function Card({ as: Tag = "div", tone, variant, padding, interactive, className, ...props }: CardProps) {
  return <Tag className={cardClasses({ tone, variant, padding, interactive, className })} {...props} />;
}
