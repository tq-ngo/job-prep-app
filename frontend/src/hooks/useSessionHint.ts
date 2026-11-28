"use client";

import { useSyncExternalStore } from "react";
import { authApi } from "@/lib/api";

function subscribe(callback: () => void) {
  window.addEventListener("focus", callback);
  document.addEventListener("visibilitychange", callback);
  return () => {
    window.removeEventListener("focus", callback);
    document.removeEventListener("visibilitychange", callback);
  };
}

function getSnapshot(): boolean {
  return authApi.hasSessionHint();
}

function getServerSnapshot(): boolean {
  return false;
}

/**
 * Client-only check for an active session hint (`csrf_token` cookie).
 * Returns `false` during SSR/ISR so marketing pages stay 100% static and cacheable.
 */
export function useSessionHint(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
