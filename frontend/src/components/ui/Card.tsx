import type { HTMLAttributes } from "react";
import { cn } from "./cn";

export type CardTone = "default" | "muted" | "elevated" | "outlined" | "filled";
export type CardPadding = "none" | "sm" | "md" | "lg";

const outlinedStyles = "bg-surface border border-outline-variant";
const filledStyles = "bg-surface-container-low border border-outline-variant";
const elevatedStyles = "bg-surface-container-lowest dark:bg-surface-container-default border border-outline-variant shadow-level-1";

const tones: Record<CardTone, string> = {
  // M3 Outlined Card
  default: outlinedStyles,
  outlined: outlinedStyles,
  // M3 Filled Card
  muted: filledStyles,
  filled: filledStyles,
  // M3 Elevated Card
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
  padding?: CardPadding;
  /** Hover affordance, for cards that are links or buttons. */
  interactive?: boolean;
  className?: string;
}

/** The class string, for a card that has to be another element (e.g. an <a>). */
export function cardClasses({ tone = "default", padding = "md", interactive, className }: CardStyle = {}) {
  return cn(
    "rounded-md",
    tones[tone],
    paddings[padding],
    interactive && "transition-all duration-200 hover:border-primary/40 hover:shadow-level-2 hover:bg-surface-container-low",
    className,
  );
}

type CardProps = HTMLAttributes<HTMLElement> & CardStyle & { as?: "div" | "section" | "article" | "li" };

/** Bordered surface for grouped content. */
export default function Card({ as: Tag = "div", tone, padding, interactive, className, ...props }: CardProps) {
  return <Tag className={cardClasses({ tone, padding, interactive, className })} {...props} />;
}
