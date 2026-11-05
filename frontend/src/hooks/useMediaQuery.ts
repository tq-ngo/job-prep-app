import { useCallback, useSyncExternalStore } from "react";

/** Matches the `lg:` breakpoint, where the job board shows list and detail side by side. */
export const DESKTOP_QUERY = "(min-width: 64rem)";

/**
 * Whether a media query matches. False on the server and during hydration
 * (the server snapshot), then the real value: use it for behaviour such as
 * what to fetch, and CSS breakpoints for what to show.
 */
export function useMediaQuery(query: string): boolean {
  const subscribe = useCallback(
    (onChange: () => void) => {
      const mql = window.matchMedia(query);
      mql.addEventListener("change", onChange);
      return () => mql.removeEventListener("change", onChange);
    },
    [query],
  );
  return useSyncExternalStore(
    subscribe,
    () => window.matchMedia(query).matches,
    () => false,
  );
}
