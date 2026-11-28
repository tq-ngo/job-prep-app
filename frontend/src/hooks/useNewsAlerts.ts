import type { NewsEvent } from "@/lib/api";
import { useSseStream } from "./useSseStream";

interface UseNewsAlertsOptions {
  /** Called whenever a daily news SSE event arrives. */
  onEvent?: (event: NewsEvent) => void;
}

export function useNewsAlerts({ onEvent }: UseNewsAlertsOptions = {}) {
  return useSseStream<NewsEvent>({
    path: "/api/v1/stream/news",
    eventName: "news",
    onEvent,
  });
}
