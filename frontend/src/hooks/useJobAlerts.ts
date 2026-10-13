import { useEffect, useRef, useState } from "react";
import { API_BASE, JobEvent, authApi } from "@/lib/api";

const MAX_RECONNECT_DELAY = 30000; // 30s cap
const MAX_RECONNECT_ATTEMPTS = 10; // then wait for focus/online rather than loop forever
const BASE_RECONNECT_DELAY = 1000; // 1s initial
// EventSource can't see HTTP status, so every error *might* be an expired
// access token. Refreshing on each one would hammer /auth/refresh while the
// network is down; once per window is enough.
const REFRESH_MIN_INTERVAL = 30000;

interface UseJobAlertsOptions {
  /** Comma-separated skill names to subscribe to (optional). */
  skills?: string;
  /** Called whenever a job SSE event arrives (optional). */
  onEvent?: (event: JobEvent) => void;
}

export function useJobAlerts({ skills = "", onEvent }: UseJobAlertsOptions = {}) {
  const [connected, setConnected] = useState(false);
  const onEventRef = useRef(onEvent);
  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);
  // Survives skill changes so a re-subscribe resumes where the last left off.
  const lastEventIdRef = useRef<string | null>(null);

  useEffect(() => {
    let es: EventSource | null = null;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let attempt = 0;
    let lastRefresh = 0;
    let disposed = false;
    // False once the session is known to be gone: stop reconnecting.
    let sessionAlive = true;

    const close = () => {
      if (es) {
        es.onerror = null;
        es.close();
        es = null;
      }
    };

    /**
     * Try to rotate the session. A routine 15-minute access-token expiry used
     * to kill live updates: the stream closed, every reconnect 401'd with the
     * same expired cookie, and the hook gave up after ~3 minutes.
     */
    const tryRefresh = async (force: boolean) => {
      if (!authApi.hasSessionHint()) {
        sessionAlive = false;
        return;
      }
      const now = Date.now();
      if (!force && now - lastRefresh < REFRESH_MIN_INTERVAL) return;
      lastRefresh = now;
      try {
        await authApi.refresh();
      } catch (err: unknown) {
        const status = (err as { response?: { status?: number } })?.response?.status;
        if (status === 401) sessionAlive = false;
        // Anything else (network down, 5xx): keep reconnecting with backoff.
      }
    };

    const connect = () => {
      close();
      if (disposed || !sessionAlive) return;

      // Auth is the HttpOnly cookie, which the browser attaches automatically
      // when withCredentials is set.
      const params = new URLSearchParams();
      if (skills) params.set("skills", skills);
      if (lastEventIdRef.current) params.set("last_event_id", lastEventIdRef.current);
      const qs = params.toString();
      es = new EventSource(
        `${API_BASE}/api/v1/stream/jobs/alerts${qs ? `?${qs}` : ""}`,
        { withCredentials: true },
      );

      es.onopen = () => {
        setConnected(true);
        attempt = 0;
      };

      // The server emits `event: job`, so listen for that name specifically
      // (onmessage only receives unnamed events).
      es.addEventListener("job", (event: MessageEvent) => {
        if (event.lastEventId) lastEventIdRef.current = event.lastEventId;
        try {
          onEventRef.current?.(JSON.parse(event.data) as JobEvent);
        } catch {
          // Malformed event data — ignore
        }
      });

      // Sent by the server just before it closes a stream whose token expired.
      es.addEventListener("auth-expired", () => {
        close();
        setConnected(false);
        void tryRefresh(true).then(connect);
      });

      es.onerror = () => {
        // EventSource fires onerror on any drop; close it ourselves so the
        // browser's own retry doesn't race ours.
        setConnected(false);
        close();
        scheduleReconnect();
      };
    };

    const scheduleReconnect = () => {
      if (disposed || !sessionAlive || attempt >= MAX_RECONNECT_ATTEMPTS) return;
      // Exponential backoff: 1s, 2s, 4s, 8s, 16s, 30s (capped)
      const delay = Math.min(BASE_RECONNECT_DELAY * 2 ** attempt, MAX_RECONNECT_DELAY);
      attempt += 1;
      timer = setTimeout(() => {
        void tryRefresh(false).then(connect);
      }, delay);
    };

    // Coming back to the tab or the network: start fresh instead of staying
    // dead after MAX_RECONNECT_ATTEMPTS.
    const revive = () => {
      if (document.visibilityState !== "visible" || es) return;
      if (timer) clearTimeout(timer);
      attempt = 0;
      sessionAlive = authApi.hasSessionHint();
      void tryRefresh(false).then(connect);
    };

    connect();
    document.addEventListener("visibilitychange", revive);
    window.addEventListener("online", revive);

    return () => {
      disposed = true;
      document.removeEventListener("visibilitychange", revive);
      window.removeEventListener("online", revive);
      if (timer) clearTimeout(timer);
      close();
    };
  }, [skills]);

  return { connected };
}
