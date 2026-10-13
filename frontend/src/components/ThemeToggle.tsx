"use client";

import { useTheme } from "@/context/ThemeContext";
import { Sun, Moon } from "lucide-react";

/**
 * Both icons are rendered and CSS (`dark:` bound to the <html> class) shows
 * the right one, so the server HTML is already correct. The toggle used to
 * render an invisible placeholder until mount and only then pick an icon.
 */
export default function ThemeToggle({ className = "" }: { className?: string }) {
  const { toggleTheme } = useTheme();

  return (
    <button
      onClick={toggleTheme}
      type="button"
      aria-label="Toggle dark mode"
      title="Toggle dark mode"
      className={`w-8 h-8 rounded border border-slate-soft hover:border-spruce-green/40 flex items-center justify-center text-foreground-muted hover:text-slate-ink transition-colors cursor-pointer ${className}`}
    >
      <Moon size={15} aria-hidden="true" className="text-slate-ink transition-transform hover:-rotate-12 dark:hidden" />
      <Sun size={15} aria-hidden="true" className="text-amber-clay transition-transform hover:rotate-45 hidden dark:block" />
    </button>
  );
}
