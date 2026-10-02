"use client";

import { useTheme } from "@/context/ThemeContext";
import { Sun, Moon } from "lucide-react";
import { useEffect, useState } from "react";

export default function ThemeToggle({ className = "" }: { className?: string }) {
  const { theme, toggleTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <div className={`w-8 h-8 rounded border border-slate-soft/50 flex items-center justify-center opacity-0 ${className}`} />
    );
  }

  return (
    <button
      onClick={toggleTheme}
      type="button"
      aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
      title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
      className={`w-8 h-8 rounded border border-slate-soft hover:border-spruce-green/40 flex items-center justify-center text-foreground-muted hover:text-slate-ink transition-colors cursor-pointer ${className}`}
    >
      {theme === "dark" ? (
        <Sun size={15} className="text-amber-clay transition-transform hover:rotate-45" />
      ) : (
        <Moon size={15} className="text-slate-ink transition-transform hover:-rotate-12" />
      )}
    </button>
  );
}
