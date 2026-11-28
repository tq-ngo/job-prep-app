import type { JobEvent } from "@/lib/api";
import { useSseStream } from "./useSseStream";

interface UseJobAlertsOptions {
  /** Comma-separated skill names to subscribe to (optional). */
  skills?: string;
  /** Called whenever a job SSE event arrives (optional). */
  onEvent?: (event: JobEvent) => void;
}

export function useJobAlerts({ skills = "", onEvent }: UseJobAlertsOptions = {}) {
  return useSseStream<JobEvent>({
    path: "/api/v1/stream/jobs/alerts",
    eventName: "job",
    query: skills ? { skills } : undefined,
    onEvent,
  });
}
