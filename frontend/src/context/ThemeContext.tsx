"use client";

import React, { createContext, useContext, useEffect, useCallback, useSyncExternalStore } from "react";

type Theme = "light" | "dark";

interface ThemeContextType {
  theme: Theme;
  toggleTheme: () => void;
  setTheme: (theme: Theme) => void;
}

const STORAGE_KEY = "jobprep_theme";
const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

/**
 * The <html> class is the single source of truth. The inline script in
 * app/layout.tsx sets it before first paint (from localStorage, else the OS
 * preference); this store just observes it. The old provider kept its own
 * state initialised to "dark" and synced it in an effect, so for a moment
 * after hydration the context disagreed with what was on screen.
 */
function subscribe(onChange: () => void) {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
  return () => observer.disconnect();
}
const getSnapshot = (): Theme =>
  document.documentElement.classList.contains("dark") ? "dark" : "light";
// The server can't know the theme; components must not render theme-
// dependent markup from this (ThemeToggle uses CSS `dark:` instead).
const getServerSnapshot = (): Theme => "light";

function readStored(): Theme | null {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    return v === "light" || v === "dark" ? v : null;
  } catch {
    return null;
  }
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const theme = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  // With no explicit choice stored, keep following the OS setting live.
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = (e: MediaQueryListEvent) => {
      if (!readStored()) document.documentElement.classList.toggle("dark", e.matches);
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const setTheme = useCallback((next: Theme) => {
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Private mode / blocked storage: still switch for this page view.
    }
    document.documentElement.classList.toggle("dark", next === "dark");
  }, []);

  const toggleTheme = useCallback(() => {
    setTheme(getSnapshot() === "dark" ? "light" : "dark");
  }, [setTheme]);

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return context;
}
