import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import LandingHero from "@/app/(marketing)/LandingHero";
import { MarketingHeaderActions } from "@/app/(marketing)/MarketingAuthActions";

describe("Marketing landing page stats & signed-in UX", () => {
  afterEach(() => {
    document.cookie = "csrf_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
  });

  it("renders live backend stats instead of dashes", () => {
    render(
      <LandingHero
        stats={{
          active_jobs: 4091,
          added_24h: 125,
          companies: 612,
          last_crawl_at: "2026-11-28T07:00:00Z",
        }}
      />,
    );

    expect(screen.getByText("4,091")).toBeInTheDocument();
    expect(screen.getAllByText("125")).toHaveLength(2);
    expect(screen.getByText("612")).toBeInTheDocument();
  });

  it("shows guest CTAs when signed out and signed-in CTAs when csrf_token cookie is present", () => {
    const { unmount } = render(
      <>
        <MarketingHeaderActions />
        <LandingHero stats={null} />
      </>,
    );
    expect(screen.getAllByRole("link", { name: /sign in/i }).length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: /create free account/i })).toHaveAttribute("href", "/register");
    unmount();

    document.cookie = "csrf_token=session-present; path=/";
    render(
      <>
        <MarketingHeaderActions />
        <LandingHero stats={null} />
      </>,
    );
    expect(screen.queryByRole("link", { name: /create free account/i })).not.toBeInTheDocument();
    const jobLinks = screen.getAllByRole("link", { name: /open job board/i });
    expect(jobLinks.length).toBeGreaterThan(0);
    expect(jobLinks[0]).toHaveAttribute("href", "/jobs");
    expect(screen.getAllByRole("link", { name: /tech news/i }).length).toBeGreaterThan(0);
  });
});
