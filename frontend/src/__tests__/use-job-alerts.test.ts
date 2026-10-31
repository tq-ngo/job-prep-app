import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { useJobAlerts } from "@/hooks/useJobAlerts";
import { authApi } from "@/lib/api";

type EventListenerFn = (e: unknown) => void;

class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  withCredentials: boolean;
  listeners: Record<string, EventListenerFn[]> = {};
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;

  constructor(url: string, init?: { withCredentials?: boolean }) {
    this.url = url;
    this.withCredentials = init?.withCredentials ?? false;
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: EventListenerFn) {
    this.listeners[type] = this.listeners[type] || [];
    this.listeners[type].push(listener);
  }

  removeEventListener(type: string, listener: EventListenerFn) {
    if (this.listeners[type]) {
      this.listeners[type] = this.listeners[type].filter((l) => l !== listener);
    }
  }

  emit(type: string, event: unknown) {
    this.listeners[type]?.forEach((l) => l(event));
  }

  close() {
    this.closed = true;
  }
}

describe("useJobAlerts SSE Hook (src/hooks/useJobAlerts.ts)", () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    global.EventSource = MockEventSource as unknown as typeof EventSource;
    vi.spyOn(authApi, "hasSessionHint").mockReturnValue(true);
    vi.spyOn(authApi, "refresh").mockResolvedValue(undefined as void);
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("connects to SSE endpoint with credentials and skills param", () => {
    const { result } = renderHook(() => useJobAlerts({ skills: "python,react" }));

    expect(MockEventSource.instances).toHaveLength(1);
    const es = MockEventSource.instances[0];
    expect(es.url).toContain("/api/v1/stream/jobs/alerts?skills=python%2Creact");
    expect(es.withCredentials).toBe(true);
    expect(result.current.connected).toBe(false);

    act(() => {
      es.onopen?.();
    });
    expect(result.current.connected).toBe(true);
  });

  it("dispatches incoming 'job' events to callback", () => {
    const onEvent = vi.fn();
    renderHook(() => useJobAlerts({ onEvent }));

    const es = MockEventSource.instances[0];
    const jobPayload = {
      kind: "created",
      id: "job-alert-1",
      title: "SWE Intern",
      company: "Meta",
      location: "Menlo Park, CA",
      skills: ["C++"],
      apply_url: "https://meta.com",
      source: "linkedin",
      is_remote: false,
    };

    act(() => {
      es.emit("job", {
        lastEventId: "evt-999",
        data: JSON.stringify(jobPayload),
      });
    });

    expect(onEvent).toHaveBeenCalledWith(jobPayload);
  });

  it("proactively refreshes session and reconnects on 'auth-expired' event", async () => {
    renderHook(() => useJobAlerts());
    const es = MockEventSource.instances[0];

    await act(async () => {
      es.emit("auth-expired", {});
    });

    expect(es.closed).toBe(true);
    expect(authApi.refresh).toHaveBeenCalled();
  });

  it("schedules reconnect with exponential backoff on onerror", async () => {
    renderHook(() => useJobAlerts());
    const es = MockEventSource.instances[0];

    act(() => {
      es.onerror?.();
    });
    expect(es.closed).toBe(true);

    // Initial reconnect delay is 1000ms
    expect(MockEventSource.instances).toHaveLength(1);
    await act(async () => {
      vi.advanceTimersByTime(1000);
      await Promise.resolve();
    });
    expect(MockEventSource.instances).toHaveLength(2);
  });

  it("cleans up EventSource and event listeners on unmount", () => {
    const { unmount } = renderHook(() => useJobAlerts());
    const es = MockEventSource.instances[0];

    unmount();
    expect(es.closed).toBe(true);
  });
});
