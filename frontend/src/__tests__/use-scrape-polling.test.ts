import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { POLL_TIMEOUT_MS, useScrapePolling } from "@/hooks/useScrapePolling";
import { tasksApi } from "@/lib/api";

const pending = { status: "PENDING", result: null, error: null };

/** Let the in-flight poll settle, then advance to the next one. */
async function tick(ms = 2000) {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
    vi.advanceTimersByTime(ms);
    await Promise.resolve();
  });
}

describe("useScrapePolling (src/hooks/useScrapePolling.ts)", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("does not poll without a task id", () => {
    const spy = vi.spyOn(tasksApi, "getStatus");
    renderHook(() => useScrapePolling(null, { onSuccess: vi.fn() }));
    expect(spy).not.toHaveBeenCalled();
  });

  it("reports progress, then success once, then stops", async () => {
    const onSuccess = vi.fn();
    const onProgress = vi.fn();
    const onError = vi.fn();
    const spy = vi
      .spyOn(tasksApi, "getStatus")
      .mockResolvedValueOnce(pending)
      .mockResolvedValueOnce({ ...pending, status: "PROGRESS", meta: { percent: 50, message: "Parsing…" } })
      .mockResolvedValueOnce({ status: "SUCCESS", result: { jobs_added: 12 }, error: null });

    renderHook(() => useScrapePolling("task-123", { onSuccess, onProgress, onError }));
    expect(spy).toHaveBeenCalledTimes(1);

    await tick();
    await tick();
    expect(onProgress).toHaveBeenCalledWith(50, "Parsing…");
    await tick();
    expect(onSuccess).toHaveBeenCalledExactlyOnceWith({ jobs_added: 12 });

    await tick(10_000);
    expect(spy).toHaveBeenCalledTimes(3);
    expect(onError).not.toHaveBeenCalled();
  });

  it("reports a FAILURE with its reason and stops", async () => {
    const onError = vi.fn();
    const spy = vi.spyOn(tasksApi, "getStatus").mockResolvedValueOnce({ status: "FAILURE", result: null, error: "Scraper rate limited" });

    renderHook(() => useScrapePolling("task-fail", { onSuccess: vi.fn(), onError }));
    await tick(10_000);

    expect(onError).toHaveBeenCalledExactlyOnceWith("The task failed: Scraper rate limited");
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it("rides out a network blip but gives up after repeated failures", async () => {
    const onError = vi.fn();
    const onSuccess = vi.fn();
    const spy = vi
      .spyOn(tasksApi, "getStatus")
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce(pending)
      .mockRejectedValue(Object.assign(new Error("offline"), { request: {} }));

    renderHook(() => useScrapePolling("task-net", { onSuccess, onError }));
    await tick(); // 1 failed, 2 pending
    await tick(); // 3 failed
    await tick(); // 4 failed
    expect(onError).not.toHaveBeenCalled();
    await tick(); // 5 failed: third in a row
    expect(onError).toHaveBeenCalledExactlyOnceWith(expect.stringMatching(/lost contact/i));

    await tick(10_000);
    expect(spy).toHaveBeenCalledTimes(5);
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it("stops at once on a 4xx (an unknown task, or someone else's)", async () => {
    const onError = vi.fn();
    const spy = vi.spyOn(tasksApi, "getStatus").mockRejectedValue({ response: { status: 404 } });

    renderHook(() => useScrapePolling("task-404", { onSuccess: vi.fn(), onError }));
    await tick(10_000);

    expect(onError).toHaveBeenCalledExactlyOnceWith("Couldn't check the task's progress.");
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it("times out instead of polling forever", async () => {
    const onError = vi.fn();
    vi.spyOn(tasksApi, "getStatus").mockResolvedValue(pending);

    renderHook(() => useScrapePolling("task-slow", { onSuccess: vi.fn(), onError }));
    await tick(POLL_TIMEOUT_MS - 1000);
    expect(onError).not.toHaveBeenCalled();
    await tick(4000);
    await tick(4000);
    expect(onError).toHaveBeenCalledExactlyOnceWith(expect.stringMatching(/longer than expected/i));
  });

  it("stops polling and stays silent after unmount", async () => {
    const onError = vi.fn();
    const spy = vi.spyOn(tasksApi, "getStatus").mockResolvedValue(pending);

    const { unmount } = renderHook(() => useScrapePolling("task-cancel", { onSuccess: vi.fn(), onError }));
    await tick();
    expect(spy).toHaveBeenCalledTimes(2);

    unmount();
    await tick(10_000);
    expect(spy).toHaveBeenCalledTimes(2);
    expect(onError).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("uses the latest handlers without restarting the poll", async () => {
    const first = vi.fn();
    const second = vi.fn();
    const spy = vi
      .spyOn(tasksApi, "getStatus")
      .mockResolvedValueOnce(pending)
      .mockResolvedValueOnce({ status: "SUCCESS", result: null, error: null });

    const { rerender } = renderHook(({ cb }) => useScrapePolling("task-x", { onSuccess: cb }), { initialProps: { cb: first } });
    rerender({ cb: second });
    await tick();
    await tick();

    expect(spy).toHaveBeenCalledTimes(2);
    expect(first).not.toHaveBeenCalled();
    expect(second).toHaveBeenCalledOnce();
  });
});
