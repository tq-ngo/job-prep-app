import { useEffect, useRef, useState, useCallback } from "react";
import { Job } from "@/lib/api";

const MAX_RECONNECT_DELAY = 30000; // 30s cap
const MAX_RECONNECT_ATTEMPTS = 10; // then give up rather than loop forever
const BASE_RECONNECT_DELAY = 1000; // 1s initial

interface UseJobAlertsOptions {
  /** Comma-separated skill names to subscribe to (optional). */
  skills?: string;
  /** Called whenever a new job SSE event arrives (optional). */
  onNewJob?: (job: Job) => void;
}

export function useJobAlerts({ skills = "", onNewJob }: UseJobAlertsOptions = {}) {
  const [newJobs, setNewJobs] = useState<Job[]>([]);
  const [connected, setConnected] = useState(false);
  const esRef = useRef<EventSource | null>(null);
  const onNewJobRef = useRef(onNewJob);
  useEffect(() => {
    onNewJobRef.current = onNewJob;
  }, [onNewJob]);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastEventIdRef = useRef<string | null>(null);

  const connect = useCallback(() => {
    // Clean up any existing connection before opening a new one
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }

    // Auth is the HttpOnly cookie, which the browser attaches automatically
    // when withCredentials is set.
    const apiUrl =
      process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const params = new URLSearchParams();
    if (skills) params.set("skills", skills);
    if (lastEventIdRef.current) params.set("last_event_id", lastEventIdRef.current);
    const qs = params.toString();
    const sseUrl = `${apiUrl}/api/v1/stream/jobs/alerts${qs ? `?${qs}` : ""}`;

    const es = new EventSource(sseUrl, { withCredentials: true });
    esRef.current = es;

    es.onopen = () => {
      setConnected(true);
      reconnectAttemptRef.current = 0; // Reset backoff on successful connect
    };

    // The server emits `event: job`, so listen for that name specifically
    // (onmessage only receives unnamed events).
    es.addEventListener("job", (event: MessageEvent) => {
      try {
        if (event.lastEventId) {
          lastEventIdRef.current = event.lastEventId;
        }
        const job: Job = JSON.parse(event.data);
        // Prepend the new job; cap list at 50 to avoid unbounded growth
        setNewJobs((prev) => [job, ...prev].slice(0, 50));
        // Read through a ref: `connect` is memoized on [skills], so calling
        // onNewJob directly captured the first render's callback forever.
        onNewJobRef.current?.(job);
      } catch {
        // Malformed event data — ignore silently
      }
    });

    es.onerror = () => {
      // EventSource fires onerror on any connection drop and enters CLOSED state.
      // We close manually to avoid double-reconnect (browser auto-retries too).
      setConnected(false);
      es.close();
      esRef.current = null;
      scheduleReconnect();
    };
  }, [skills]);

  const scheduleReconnect = useCallback(() => {
    const attempt = reconnectAttemptRef.current;
    if (attempt >= MAX_RECONNECT_ATTEMPTS) {
      // An expired or revoked session 401s forever; retrying every 30s
      // indefinitely just burns requests.
      return;
    }
    // Exponential backoff: 1s, 2s, 4s, 8s, 16s, 30s (capped)
    const delay = Math.min(
      BASE_RECONNECT_DELAY * Math.pow(2, attempt),
      MAX_RECONNECT_DELAY
    );
    reconnectAttemptRef.current = attempt + 1;

    reconnectTimerRef.current = setTimeout(() => {
      connect();
    }, delay);
  }, [connect]);

  useEffect(() => {
    connect();

    return () => {
      // Cleanup on unmount: cancel pending reconnect and close SSE connection
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
      if (esRef.current) {
        // Null out onerror BEFORE closing to prevent scheduleReconnect from
        // firing during intentional cleanup (same pattern as WebSocket onclose).
        esRef.current.onerror = null;
        esRef.current.close();
        esRef.current = null;
      }
    };
  }, [connect]);

  /** Clear the accumulated new jobs list (e.g. after user views them). */
  const clearNewJobs = useCallback(() => setNewJobs([]), []);

  return { newJobs, connected, clearNewJobs };
}