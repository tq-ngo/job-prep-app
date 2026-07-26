import { useEffect, useRef } from "react";
import { tasksApi } from "@/lib/api";

export function useScrapePolling(
  taskId: string | null, 
  onComplete: () => void,
  onProgress?: (percent: number, message: string) => void
) {
  // Refs to avoid re-triggering the effect when callbacks change
  const onCompleteRef = useRef(onComplete);
  const onProgressRef = useRef(onProgress);
  onCompleteRef.current = onComplete;
  onProgressRef.current = onProgress;

  useEffect(() => {
    if (!taskId) return;

    let cancelled = false;

    async function poll() {
      if (cancelled) return;

      try {
        const result = await tasksApi.getStatus(taskId!);

        if (cancelled) return;

        if (result.status === "SUCCESS") {
          onCompleteRef.current();
          return; // stop polling
        } else if (result.status === "FAILURE") {
          console.error("Scraping task failed:", result.error);
          return; // stop polling
        } else if (result.status === "PROGRESS" && result.meta && onProgressRef.current) {
          onProgressRef.current(result.meta.percent, result.meta.message);
        }
      } catch (error) {
        if (cancelled) return;
        console.error("Polling error:", error);
        return; // stop polling on network error
      }

      // Schedule next poll only after current one finishes (no overlap)
      if (!cancelled) {
        setTimeout(poll, 2000);
      }
    }

    // Start first poll immediately
    poll();

    return () => {
      cancelled = true;
    };
  }, [taskId]);
}
