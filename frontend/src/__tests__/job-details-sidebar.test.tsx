import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import JobDetailsSidebar from "@/components/JobDetailsSidebar";
import { Job } from "@/lib/api";

const mockJob: Job = {
  id: "job-full-1",
  title: "Full-Stack Engineering Intern",
  company: "Linear",
  location: "New York, NY",
  source: "github",
  apply_url: "https://linear.app/careers",
  description: "### About The Team\nJoin our team building modern issue tracking.\n\n| Skill | Proficiency |\n|---|---|\n| React | Expert |\n\n[Apply Directly](https://linear.app)",
  skills: ["React", "TypeScript", "GraphQL"],
  salary_min: 60,
  salary_max: 75,
  salary_currency: "USD",
  salary_period: "hour",
  is_remote: true,
  posted_at: "2026-03-01T00:00:00Z",
  scraped_at: "2026-03-01T00:00:00Z",
};

describe("JobDetailsSidebar Component (src/components/JobDetailsSidebar.tsx)", () => {
  let initialOverflow: string;

  beforeEach(() => {
    initialOverflow = document.body.style.overflow;
  });

  afterEach(() => {
    document.body.style.overflow = initialOverflow;
  });

  it("renders with proper WAI-ARIA dialog attributes when open", () => {
    render(<JobDetailsSidebar job={mockJob} open={true} onClose={() => {}} />);

    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeInTheDocument();
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAccessibleName("Full-Stack Engineering Intern");
  });

  it("sets initial focus to the close drawer button when opened", () => {
    render(<JobDetailsSidebar job={mockJob} open={true} onClose={() => {}} />);

    const closeBtn = screen.getByRole("button", { name: /close job details/i });
    expect(closeBtn).toHaveFocus();
  });

  it("calls onClose when Escape key is pressed", async () => {
    const handleClose = vi.fn();
    const user = userEvent.setup();

    render(<JobDetailsSidebar job={mockJob} open={true} onClose={handleClose} />);

    await user.keyboard("{Escape}");
    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose when clicking the backdrop overlay", () => {
    const handleClose = vi.fn();
    const { container } = render(
      <JobDetailsSidebar job={mockJob} open={true} onClose={handleClose} />
    );

    const backdrop = container.querySelector(".fixed.inset-0");
    expect(backdrop).toBeInTheDocument();
    fireEvent.click(backdrop!);
    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it("locks body scroll on open and restores on close", () => {
    const { rerender } = render(
      <JobDetailsSidebar job={mockJob} open={true} onClose={() => {}} />
    );
    expect(document.body.style.overflow).toBe("hidden");

    rerender(<JobDetailsSidebar job={mockJob} open={false} onClose={() => {}} />);
    expect(document.body.style.overflow).toBe("");
  });

  it("formats hourly and annual salary correctly", () => {
    const { rerender } = render(
      <JobDetailsSidebar job={mockJob} open={true} onClose={() => {}} />
    );
    expect(screen.getByText(/\$60 – \$75\/hr/)).toBeInTheDocument();

    const yearlyJob: Job = {
      ...mockJob,
      salary_min: 120000,
      salary_max: 130000,
      salary_period: "year",
    };
    rerender(<JobDetailsSidebar job={yearlyJob} open={true} onClose={() => {}} />);
    expect(screen.getByText(/\$120,000 – \$130,000\/yr/)).toBeInTheDocument();

    const unlistedJob: Job = {
      ...mockJob,
      salary_min: null,
      salary_max: null,
    };
    rerender(<JobDetailsSidebar job={unlistedJob} open={true} onClose={() => {}} />);
    expect(screen.getByText(/Not listed/)).toBeInTheDocument();
  });

  it("renders sanitized GFM markdown including tables and secure external links", () => {
    render(<JobDetailsSidebar job={mockJob} open={true} onClose={() => {}} />);

    expect(
      screen.getByRole("heading", { level: 4, name: "About The Team" })
    ).toBeInTheDocument();

    expect(screen.getByRole("table")).toBeInTheDocument();

    const link = screen.getByRole("link", { name: "Apply Directly" });
    expect(link).toHaveAttribute("href", "https://linear.app");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer nofollow");
  });
});
