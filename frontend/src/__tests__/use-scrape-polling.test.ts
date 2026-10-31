import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { useScrapePolling } from "@/hooks/useScrapePolling";
import { tasksApi } from "@/lib/api";

describe("useScrapePolling Hook (src/hooks/useScrapePolling.ts)", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("does not start polling when taskId is null", () => {
    const getStatusSpy = vi.spyOn(tasksApi, "getStatus");
    const onComplete = vi.fn();

    renderHook(() => useScrapePolling(null, onComplete));
    expect(getStatusSpy).not.toHaveBeenCalled();
  });

  it("polls until status is SUCCESS, triggers onComplete, and stops polling", async () => {
    const onComplete = vi.fn();
    const onProgress = vi.fn();

    const getStatusSpy = vi.spyOn(tasksApi, "getStatus")
      .mockResolvedValueOnce({ status: "PENDING", result: null, error: null })
      .mockResolvedValueOnce({
        status: "PROGRESS",
        result: null,
        error: null,
        meta: { percent: 50, message: "Parsing job descriptions..." },
      })
      .mockResolvedValueOnce({ status: "SUCCESS", result: { jobs_added: 12 }, error: null });

    renderHook(() => useScrapePolling("task-123", onComplete, onProgress));

    // First call happens immediately
    expect(getStatusSpy).toHaveBeenCalledTimes(1);
    await act(async () => {
      await Promise.resolve();
    });

    // Advance 2s for second poll
    await act(async () => {
      vi.advanceTimersByTime(2000);
      await Promise.resolve();
    });
    expect(getStatusSpy).toHaveBeenCalledTimes(2);
    expect(onProgress).toHaveBeenCalledWith(50, "Parsing job descriptions...");

    // Advance 2s for third poll
    await act(async () => {
      vi.advanceTimersByTime(2000);
      await Promise.resolve();
    });
    expect(getStatusSpy).toHaveBeenCalledTimes(3);
    expect(onComplete).toHaveBeenCalledTimes(1);

    // No further polls should occur
    await act(async () => {
      vi.advanceTimersByTime(4000);
    });
    expect(getStatusSpy).toHaveBeenCalledTimes(3);
  });

  it("halts polling immediately when status is FAILURE", async () => {
    const onComplete = vi.fn();
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    const getStatusSpy = vi.spyOn(tasksApi, "getStatus").mockResolvedValueOnce({
      status: "FAILURE",
      result: null,
      error: "Scraper rate limited",
    });

    renderHook(() => useScrapePolling("task-fail", onComplete));

    await act(async () => {
      await Promise.resolve();
    });
    expect(getStatusSpy).toHaveBeenCalledTimes(1);
    expect(onComplete).not.toHaveBeenCalled();

    await act(async () => {
      vi.advanceTimersByTime(4000);
    });
    expect(getStatusSpy).toHaveBeenCalledTimes(1);
    expect(consoleSpy).toHaveBeenCalledWith("Scraping task failed:", "Scraper rate limited");
  });

  it("cancels future polls when component unmounts", async () => {
    const getStatusSpy = vi.spyOn(tasksApi, "getStatus").mockResolvedValue({
      status: "PENDING",
      result: null,
      error: null,
    });

    const { unmount } = renderHook(() => useScrapePolling("task-cancel", () => {}));

    await act(async () => {
      await Promise.resolve();
    });
    expect(getStatusSpy).toHaveBeenCalledTimes(1);

    unmount();

    await act(async () => {
      vi.advanceTimersByTime(5000);
    });
    // Still 1: cancelled before second poll could execute
    expect(getStatusSpy).toHaveBeenCalledTimes(1);
  });
});

