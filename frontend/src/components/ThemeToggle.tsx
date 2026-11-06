"use client";

import { useTheme } from "@/context/ThemeContext";
import { Sun, Moon } from "lucide-react";
import { Button } from "@/components/ui/Button";

/**
 * Both icons are rendered and CSS (`dark:` bound to the <html> class) shows
 * the right one, so the server HTML is already correct. The toggle used to
 * render an invisible placeholder until mount and only then pick an icon.
 */
export default function ThemeToggle({ className = "" }: { className?: string }) {
  const { theme, toggleTheme } = useTheme();

  return (
    <Button
      variant="secondary"
      size="icon"
      onClick={toggleTheme}
      aria-label="Dark mode"
      aria-pressed={theme === "dark"}
      title="Toggle dark mode"
      className={className}
    >
      <Moon size={15} aria-hidden="true" className="text-slate-ink transition-transform hover:-rotate-12 dark:hidden" />
      <Sun size={15} aria-hidden="true" className="text-amber-clay transition-transform hover:rotate-45 hidden dark:block" />
    </Button>
  );
}
