import { useEffect, useRef } from "react";
import { tasksApi } from "@/lib/api";
import { errorStatus } from "@/lib/errors";

const POLL_INTERVAL_MS = 2000;
/** Scrapes are capped at 30 min server-side, but nobody watches a spinner that long. */
export const POLL_TIMEOUT_MS = 10 * 60 * 1000;
/** Consecutive network failures tolerated before giving up (a blip shouldn't). */
const MAX_NETWORK_ERRORS = 3;

export interface ScrapePollingHandlers {
  onSuccess: (result: unknown) => void;
  onProgress?: (percent: number, message: string) => void;
  /** The task failed, couldn't be checked, or ran past the timeout. */
  onError?: (message: string) => void;
}

/**
 * Poll a Celery task until it finishes. Exactly one of onSuccess/onError
 * fires per task id, and nothing fires after unmount or an id change.
 *
 * It used to stop silently on FAILURE or the first network error, and poll
 * forever otherwise, so the caller's "Syncing…" button never came back.
 */
export function useScrapePolling(taskId: string | null, handlers: ScrapePollingHandlers) {
  // Latest handlers without re-running the effect (synced in an effect:
  // writing refs during render is unsafe under concurrent rendering).
  const handlersRef = useRef(handlers);
  useEffect(() => {
    handlersRef.current = handlers;
  });

  useEffect(() => {
    if (!taskId) return;

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let networkErrors = 0;
    const deadline = Date.now() + POLL_TIMEOUT_MS;

    const fail = (message: string) => {
      if (!cancelled) handlersRef.current.onError?.(message);
    };

    async function poll() {
      if (cancelled) return;
      if (Date.now() > deadline) {
        fail("This is taking longer than expected. It may still finish in the background; check back later.");
        return;
      }

      try {
        const result = await tasksApi.getStatus(taskId!);
        if (cancelled) return;
        networkErrors = 0;

        if (result.status === "SUCCESS") {
          handlersRef.current.onSuccess(result.result);
          return;
        }
        if (result.status === "FAILURE" || result.status === "REVOKED") {
          fail(result.error ? `The task failed: ${result.error}` : "The task failed.");
          return;
        }
        if (result.status === "PROGRESS" && result.meta) {
          handlersRef.current.onProgress?.(result.meta.percent, result.meta.message);
        }
      } catch (err) {
        if (cancelled) return;
        const status = errorStatus(err);
        // 4xx (unknown task, not ours) won't fix itself; network errors and
        // 5xx might, so allow a few in a row.
        if (status !== undefined && status < 500 && status !== 429) {
          fail("Couldn't check the task's progress.");
          return;
        }
        if (++networkErrors >= MAX_NETWORK_ERRORS) {
          fail("Lost contact with the server while checking progress. The task may still finish; refresh later.");
          return;
        }
      }

      // Next poll only after this one finishes, so they never overlap.
      if (!cancelled) timer = setTimeout(poll, POLL_INTERVAL_MS);
    }

    poll();

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [taskId]);
}
