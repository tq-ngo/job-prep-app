import { useEffect, useRef, useState } from "react";
import { API_BASE, authApi } from "@/lib/api";

const MAX_RECONNECT_DELAY = 30000;
const MAX_RECONNECT_ATTEMPTS = 10;
const BASE_RECONNECT_DELAY = 1000;
const REFRESH_MIN_INTERVAL = 30000;

interface UseSseStreamOptions<TEvent> {
  /** Path relative to API_BASE, e.g. `/api/v1/stream/news`. */
  path: string;
  /** SSE event name to listen for (`job` or `news`). */
  eventName: string;
  /** Extra static query parameters (e.g. `skills=...`). */
  query?: Record<string, string | undefined>;
  /** Called whenever a matching SSE event arrives. */
  onEvent?: (event: TEvent) => void;
}

/**
 * Shared cookie-authenticated SSE stream hook with token-refresh & backoff.
 */
export function useSseStream<TEvent>({
  path,
  eventName,
  query,
  onEvent,
}: UseSseStreamOptions<TEvent>) {
  const [connected, setConnected] = useState(false);
  const onEventRef = useRef(onEvent);
  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);
  const lastEventIdRef = useRef<string | null>(null);
  const queryKey = JSON.stringify(query ?? {});

  useEffect(() => {
    if (typeof EventSource === "undefined") return;

    let es: EventSource | null = null;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let attempt = 0;
    let lastRefresh = 0;
    let disposed = false;
    let sessionAlive = true;

    const close = () => {
      if (es) {
        es.onerror = null;
        es.close();
        es = null;
      }
    };

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
        if (status === 401 || status === 403) sessionAlive = false;
      }
    };

    const connect = () => {
      close();
      if (disposed || !sessionAlive) return;

      const params = new URLSearchParams();
      const parsedQuery = JSON.parse(queryKey) as Record<string, string | undefined>;
      for (const [k, v] of Object.entries(parsedQuery)) {
        if (v) params.set(k, v);
      }
      if (lastEventIdRef.current) params.set("last_event_id", lastEventIdRef.current);
      const qs = params.toString();
      es = new EventSource(`${API_BASE}${path}${qs ? `?${qs}` : ""}`, {
        withCredentials: true,
      });

      es.onopen = () => {
        setConnected(true);
        attempt = 0;
      };

      es.addEventListener(eventName, (event: MessageEvent) => {
        if (event.lastEventId) lastEventIdRef.current = event.lastEventId;
        try {
          onEventRef.current?.(JSON.parse(event.data) as TEvent);
        } catch {
          // Malformed event data — ignore
        }
      });

      es.addEventListener("auth-expired", () => {
        close();
        setConnected(false);
        void tryRefresh(true).then(connect);
      });

      es.onerror = () => {
        setConnected(false);
        close();
        scheduleReconnect();
      };
    };

    const scheduleReconnect = () => {
      if (disposed || !sessionAlive || attempt >= MAX_RECONNECT_ATTEMPTS) return;
      const delay = Math.min(BASE_RECONNECT_DELAY * 2 ** attempt, MAX_RECONNECT_DELAY);
      attempt += 1;
      timer = setTimeout(() => {
        void tryRefresh(false).then(connect);
      }, delay);
    };

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
  }, [path, eventName, queryKey]);

  return { connected };
}
