import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import JobDetailPane from "@/components/jobs/JobDetailPane";
import type { Job } from "@/lib/api";

const job: Job = {
  id: "job-full-1",
  title: "Full-Stack Engineering Intern",
  company: "Linear",
  location: "New York, NY",
  source: "github",
  apply_url: "https://linear.app/careers",
  description:
    "### About The Team\nJoin our team building modern issue tracking.\n\n| Skill | Proficiency |\n|---|---|\n| React | Expert |\n\n[Apply Directly](https://linear.app)\n\n<script>alert(1)</script>",
  skills: ["React", "TypeScript"],
  salary_min: 60,
  salary_max: 75,
  salary_currency: "USD",
  salary_period: "hour",
  is_remote: true,
  posted_at: "2026-03-01T00:00:00Z",
  scraped_at: "2026-03-01T00:00:00Z",
};

function renderPane(props: Partial<Parameters<typeof JobDetailPane>[0]> = {}) {
  const focusTitleRequestRef = { current: false };
  const onBack = vi.fn();
  const utils = render(
    <JobDetailPane
      job={job}
      descriptionLoading={false}
      loading={false}
      unavailable={false}
      onBack={onBack}
      focusTitleRequestRef={focusTitleRequestRef}
      {...props}
    />,
  );
  return { ...utils, onBack, focusTitleRequestRef };
}

describe("JobDetailPane", () => {
  it("is a region named by the job title, not a modal dialog", () => {
    renderPane();
    expect(screen.getByRole("region", { name: job.title })).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("shows company, pay, skills and an Apply link that opens off-site safely", () => {
    renderPane();
    expect(screen.getByText("Linear")).toBeInTheDocument();
    expect(screen.getByText("$60 – $75/hr")).toBeInTheDocument();
    expect(screen.getByText("TypeScript")).toBeInTheDocument();
    const apply = screen.getByRole("link", { name: /^apply$/i });
    expect(apply).toHaveAttribute("href", job.apply_url);
    expect(apply).toHaveAttribute("target", "_blank");
    expect(apply).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("renders the sanitized GFM description, with headings under the title", async () => {
    const { container } = renderPane();
    expect(await screen.findByRole("heading", { level: 4, name: "About The Team" })).toBeInTheDocument();
    expect(screen.getByRole("table")).toBeInTheDocument();
    const link = screen.getByRole("link", { name: "Apply Directly" });
    expect(link).toHaveAttribute("rel", "noopener noreferrer nofollow");
    // Raw HTML in the Markdown stays text; it's never turned into elements.
    expect(container.querySelector("script")).toBeNull();
  });

  it("shows a loading state while the description is fetched", () => {
    renderPane({ job: { ...job, description: null }, descriptionLoading: true });
    expect(screen.getByRole("status")).toHaveTextContent("Loading description");
  });

  it("links to the posting when there's no description", () => {
    renderPane({ job: { ...job, description: null } });
    expect(screen.getByRole("link", { name: /view the posting/i })).toHaveAttribute("href", job.apply_url);
  });

  it("explains a job that can't be loaded", () => {
    renderPane({ job: null, unavailable: true });
    expect(screen.getByText("This job isn't available")).toBeInTheDocument();
  });

  it("calls onBack from the Back to results button", async () => {
    const { onBack } = renderPane();
    await userEvent.setup().click(screen.getByRole("button", { name: /back to results/i }));
    expect(onBack).toHaveBeenCalledTimes(1);
  });

  it("moves focus to the title only when asked, once", () => {
    const focusTitleRequestRef = { current: true };
    const { rerender } = render(
      <JobDetailPane job={job} descriptionLoading={false} loading={false} unavailable={false} onBack={() => {}} focusTitleRequestRef={focusTitleRequestRef} />,
    );
    const title = screen.getByRole("heading", { level: 2, name: job.title });
    expect(title).toHaveFocus();
    expect(focusTitleRequestRef.current).toBe(false);

    title.blur();
    rerender(
      <JobDetailPane job={{ ...job, id: "other", title: "Other" }} descriptionLoading={false} loading={false} unavailable={false} onBack={() => {}} focusTitleRequestRef={focusTitleRequestRef} />,
    );
    expect(screen.getByRole("heading", { level: 2, name: "Other" })).not.toHaveFocus();
  });
});
