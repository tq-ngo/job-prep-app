import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BentoSSECard, InteractiveLiveCard } from "@/app/(marketing)/LandingDemos";

function setReducedMotion(reduce: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: reduce && query.includes("reduce"),
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  })) as unknown as typeof window.matchMedia;
}

afterEach(() => {
  vi.useRealTimers();
  setReducedMotion(false);
});

describe("BentoSSECard", () => {
  it("never changes the real 24h figure when simulating events", async () => {
    render(<BentoSSECard initialCount={128} />);
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /simulate a live event/i }));
    await user.click(screen.getByRole("button", { name: /simulate a live event/i }));

    expect(screen.getByText("128")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("clears its animation timer on unmount", async () => {
    vi.useFakeTimers();
    const { unmount } = render(<BentoSSECard initialCount={null} />);
    act(() => screen.getByRole("button", { name: /simulate/i }).click());
    expect(vi.getTimerCount()).toBe(1);
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });
});

describe("InteractiveLiveCard", () => {
  const firstTitle = () => screen.getAllByText(/intern/i)[0].textContent;

  it("rotates sample jobs by default", () => {
    vi.useFakeTimers();
    render(<InteractiveLiveCard />);
    const before = firstTitle();
    act(() => vi.advanceTimersByTime(3000));
    expect(firstTitle()).not.toBe(before);
  });

  it("starts paused for people who prefer reduced motion, and can be resumed", () => {
    setReducedMotion(true);
    vi.useFakeTimers();
    render(<InteractiveLiveCard />);
    const before = firstTitle();
    act(() => vi.advanceTimersByTime(6000));
    expect(firstTitle()).toBe(before);

    act(() => screen.getByRole("button", { name: "Resume preview" }).click());
    act(() => vi.advanceTimersByTime(3000));
    expect(firstTitle()).not.toBe(before);
  });

  it("exposes the filter chips as toggles", async () => {
    render(<InteractiveLiveCard />);
    const quant = screen.getByRole("button", { name: "Quant" });
    expect(quant).toHaveAttribute("aria-pressed", "false");
    await userEvent.setup().click(quant);
    expect(quant).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("status")).toHaveTextContent(/visible/);
  });
});
