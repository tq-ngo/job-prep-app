import type { HTMLAttributes } from "react";
import { cn } from "./cn";

export type CardTone = "default" | "muted" | "elevated";
export type CardPadding = "none" | "sm" | "md" | "lg";

const tones: Record<CardTone, string> = {
  // M3 Outlined Card
  default: "bg-background border border-slate-soft",
  // M3 Filled Card
  muted: "bg-neutral-soft border border-slate-soft/70",
  // M3 Elevated Card
  elevated: "bg-neutral-soft border border-slate-soft/80 shadow-card",
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
    "rounded-card",
    tones[tone],
    paddings[padding],
    interactive && "transition-all duration-200 hover:border-spruce-green/40 hover:shadow-m3-1",
    className,
  );
}

type CardProps = HTMLAttributes<HTMLElement> & CardStyle & { as?: "div" | "section" | "article" | "li" };

/** Bordered surface for grouped content. */
export default function Card({ as: Tag = "div", tone, padding, interactive, className, ...props }: CardProps) {
  return <Tag className={cardClasses({ tone, padding, interactive, className })} {...props} />;
}
