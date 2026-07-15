import { useEffect } from "react";
import { tasksApi } from "@/lib/api";

export function useScrapePolling(taskId: string | null, onComplete: () => void) {
  useEffect(() => {
    if (!taskId) return;

    const pollInterval = setInterval(async () => {
      try {
        const result = await tasksApi.getStatus(taskId);

        if (result.status === "SUCCESS") {
          clearInterval(pollInterval);
          onComplete();
        } else if (result.status === "FAILURE") {
          clearInterval(pollInterval);
          console.error("Scraping task failed:", result.error);
        }
      } catch (error) {
        clearInterval(pollInterval);
        console.error("Polling error:", error);
      }
    }, 2000);

    return () => clearInterval(pollInterval);
  }, [taskId, onComplete]);
}
