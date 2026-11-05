import type { HTMLAttributes } from "react";
import { cn } from "./cn";

export type CardTone = "default" | "muted";
export type CardPadding = "none" | "sm" | "md" | "lg";

const tones: Record<CardTone, string> = {
  default: "bg-background",
  muted: "bg-neutral-soft",
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
    "rounded-card border border-slate-soft",
    tones[tone],
    paddings[padding],
    interactive && "transition-colors hover:border-spruce-green/30",
    className,
  );
}

type CardProps = HTMLAttributes<HTMLElement> & CardStyle & { as?: "div" | "section" | "article" | "li" };

/** Bordered surface for grouped content. */
export default function Card({ as: Tag = "div", tone, padding, interactive, className, ...props }: CardProps) {
  return <Tag className={cardClasses({ tone, padding, interactive, className })} {...props} />;
}
