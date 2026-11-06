import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import JobFeed from "@/app/(app)/jobs/JobFeed";
import { jobsApi, tasksApi, type Job, type JobEvent, type JobListResponse } from "@/lib/api";
import { parseJobFilters, type JobFilters } from "@/lib/job-filters";

// Next syncs useSearchParams with window.history.pushState/replaceState and
// with Back/Forward. Reproduce that contract: the hook reads the real URL and
// re-renders whenever history changes it.
const urlStore = vi.hoisted(() => {
  const listeners = new Set<() => void>();
  return { listeners, notify: () => listeners.forEach((l) => l()) };
});

vi.mock("next/navigation", async () => {
  const React = await import("react");
  const subscribe = (l: () => void) => {
    urlStore.listeners.add(l);
    window.addEventListener("popstate", l);
    return () => {
      urlStore.listeners.delete(l);
      window.removeEventListener("popstate", l);
    };
  };
  return {
    usePathname: () => "/jobs",
    useSearchParams: () => {
      const search = React.useSyncExternalStore(subscribe, () => window.location.search, () => "");
      return React.useMemo(() => new URLSearchParams(search), [search]);
    },
  };
});

let emitJobEvent: ((event: JobEvent) => void) | undefined;
vi.mock("@/hooks/useJobAlerts", () => ({
  useJobAlerts: ({ onEvent }: { onEvent?: (event: JobEvent) => void } = {}) => {
    emitJobEvent = onEvent;
    return { connected: true };
  },
}));

const item = (id: string, title: string, company: string, extra: Partial<Job> = {}) => ({
  id,
  title,
  company,
  location: "Boston, MA",
  source: "github",
  apply_url: `https://${company.toLowerCase()}.example/apply`,
  skills: ["Go", "Kubernetes", "SQL", "Rust"],
  salary_min: 55,
  salary_max: 65,
  salary_currency: "USD",
  salary_period: "hour" as const,
  is_remote: false,
  posted_at: "2026-03-01T00:00:00Z",
  scraped_at: "2026-03-01T00:00:00Z",
  ...extra,
});

const feed = (overrides: Partial<JobListResponse> = {}): JobListResponse => ({
  items: [item("j-1", "Backend Intern", "Datadog"), item("j-2", "Frontend Intern", "Vercel", { is_remote: true })],
  total: 2,
  page: 1,
  page_size: 30,
  pages: 1,
  ...overrides,
});

const fullJob = (id: string): Job => {
  const row = feed().items.find((j) => j.id === id)!;
  return { ...row, description: `## About ${row.company}\nWe build things.` };
};

function setViewport(desktop: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: desktop,
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  })) as unknown as typeof window.matchMedia;
}

/** Render the feed for the current URL, seeded like the server page does. */
function renderFeed({
  data = feed(),
  seedFilters,
}: { data?: JobListResponse | null; seedFilters?: JobFilters } = {}) {
  const urlFilters = parseJobFilters((k) => new URLSearchParams(window.location.search).get(k));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <JobFeed initialData={data ?? undefined} initialFilters={data ? (seedFilters ?? urlFilters) : undefined} />
    </QueryClientProvider>,
  );
}

const results = () => screen.getByRole("list", { name: "Job results" });
const link = (title: RegExp) => within(results()).getByRole("link", { name: title });
const search = () => new URLSearchParams(window.location.search);

const realPush = window.history.pushState.bind(window.history);
const realReplace = window.history.replaceState.bind(window.history);
let pushSpy: ReturnType<typeof vi.spyOn>;
let replaceSpy: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  realReplace(null, "", "/jobs");
  setViewport(false);
  pushSpy = vi.spyOn(window.history, "pushState").mockImplementation((...args) => {
    realPush(...args);
    urlStore.notify();
  });
  replaceSpy = vi.spyOn(window.history, "replaceState").mockImplementation((...args) => {
    realReplace(...args);
    urlStore.notify();
  });
  vi.spyOn(jobsApi, "get").mockImplementation(async (id) => fullJob(id));
  window.scrollTo = vi.fn() as unknown as typeof window.scrollTo;
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("JobFeed list", () => {
  it("renders the server-seeded rows without refetching", () => {
    const listSpy = vi.spyOn(jobsApi, "list");
    renderFeed();

    expect(link(/Backend Intern/)).toBeInTheDocument();
    expect(link(/Frontend Intern/)).toBeInTheDocument();
    expect(screen.getByText("2 roles")).toBeInTheDocument();
    expect(listSpy).not.toHaveBeenCalled();
  });

  it("shows pay, location, up to three skills and the source on each row", () => {
    renderFeed();
    const row = link(/Backend Intern/);
    expect(row).toHaveTextContent("$55 – $65/hr");
    expect(row).toHaveTextContent("Boston, MA");
    expect(row).toHaveTextContent("github");
    expect(within(row).getByText("SQL")).toBeInTheDocument();
    expect(within(row).queryByText("Rust")).not.toBeInTheDocument();
  });

  it("restores filters from the URL into the controls", () => {
    realReplace(null, "", "/jobs?category=Quant&q=intern&remote=true");
    vi.spyOn(jobsApi, "list");
    renderFeed();

    expect(screen.getByLabelText("Category")).toHaveValue("Quant");
    expect(screen.getByRole("searchbox", { name: /search role/i })).toHaveValue("intern");
    expect(screen.getByRole("button", { name: "Remote" })).toHaveAttribute("aria-pressed", "true");
    expect(jobsApi.list).not.toHaveBeenCalled();
  });

  it("writes a filter change to the URL, resetting page and selection", async () => {
    realReplace(null, "", "/jobs?page=2&jobId=j-1");
    const listSpy = vi.spyOn(jobsApi, "list").mockResolvedValue(feed());
    renderFeed();

    fireEvent.change(screen.getByLabelText("Category"), { target: { value: "FAANG+" } });

    expect(replaceSpy).toHaveBeenCalled();
    expect(pushSpy).not.toHaveBeenCalled();
    expect(search().get("category")).toBe("FAANG+");
    expect(search().has("page")).toBe(false);
    expect(search().has("jobId")).toBe(false);
    await waitFor(() => expect(listSpy).toHaveBeenCalledWith(expect.objectContaining({ category: "FAANG+", page: 1 })));
  });

  it("debounces search into the URL", async () => {
    const listSpy = vi.spyOn(jobsApi, "list").mockResolvedValue(feed());
    renderFeed();

    await userEvent.setup().type(screen.getByRole("searchbox", { name: /search role/i }), "rust");
    expect(search().has("q")).toBe(false);
    await waitFor(() => expect(search().get("q")).toBe("rust"));
    await waitFor(() => expect(listSpy).toHaveBeenCalledWith(expect.objectContaining({ q: "rust" })));
  });

  it("only uses the server seed for the filters it was fetched with", async () => {
    realReplace(null, "", "/jobs?page=2");
    const listSpy = vi.spyOn(jobsApi, "list").mockResolvedValue(feed({ page: 2, pages: 2 }));
    renderFeed({ seedFilters: parseJobFilters(() => null) }); // seeded for page 1

    await waitFor(() => expect(listSpy).toHaveBeenCalledWith(expect.objectContaining({ page: 2 })));
  });

  it("keeps the current rows on screen while the next page loads", async () => {
    vi.spyOn(jobsApi, "list").mockImplementation(() => new Promise(() => {}));
    renderFeed({ data: feed({ total: 60, pages: 2 }) });

    await userEvent.setup().click(screen.getByRole("button", { name: "Next" }));

    expect(pushSpy).toHaveBeenCalled();
    expect(search().get("page")).toBe("2");
    expect(link(/Backend Intern/)).toBeInTheDocument();
    expect(results()).toHaveAttribute("aria-busy", "true");
    expect(screen.queryByText("Loading jobs")).not.toBeInTheDocument();
  });

  it("shows an error with Retry instead of an empty board when loading fails", async () => {
    const listSpy = vi.spyOn(jobsApi, "list").mockRejectedValue(new Error("network"));
    renderFeed({ data: null });

    expect(await screen.findByRole("alert")).toHaveTextContent(/couldn't load jobs/i);
    expect(screen.queryByText("No positions found")).not.toBeInTheDocument();

    await userEvent.setup().click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(listSpy).toHaveBeenCalledTimes(2));
  });

  it("offers to clear filters when they match nothing", async () => {
    realReplace(null, "", "/jobs?source=linkedin&q=zzz");
    renderFeed({ data: feed({ items: [], total: 0, pages: 0 }) });

    expect(screen.getByText("No positions found")).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: "Clear filters" }));
    expect(window.location.search).toBe("");
  });

  it("reports a refresh that can't start, and resets the button", async () => {
    vi.spyOn(jobsApi, "triggerScrape").mockRejectedValue({ response: { status: 429 } });
    renderFeed();
    await userEvent.setup().click(screen.getByRole("button", { name: "Refresh" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/too many attempts/i);
    expect(screen.getByRole("button", { name: "Refresh" })).toBeEnabled();
  });

  it("reports a refresh whose task fails, instead of spinning forever", async () => {
    vi.spyOn(jobsApi, "triggerScrape").mockResolvedValue({ task_id: "t-1", status: "accepted" });
    vi.spyOn(tasksApi, "getStatus").mockResolvedValue({ status: "FAILURE", result: null, error: "GitHub rate limit" });
    renderFeed();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Refresh" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Refresh didn't finish. The task failed: GitHub rate limit");
    expect(screen.getByRole("button", { name: "Refresh" })).toBeEnabled();
    await user.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("counts live 'created' events into a new-jobs button", () => {
    renderFeed();
    expect(screen.queryByText(/new job/i)).not.toBeInTheDocument();

    const event: JobEvent = { kind: "created", id: "j-3", title: "Security Intern", company: "Cloudflare", location: null, skills: [], apply_url: "https://x", source: "github", is_remote: false };
    act(() => emitJobEvent?.(event));
    expect(screen.getByRole("button", { name: /1 new job/i })).toBeInTheDocument();
    act(() => emitJobEvent?.({ ...event, id: "j-4" }));
    act(() => emitJobEvent?.({ ...event, id: "j-5", kind: "enriched" }));
    expect(screen.getByRole("button", { name: /2 new jobs/i })).toBeInTheDocument();
  });
});

describe("JobFeed selection", () => {
  it("shows the first result in the detail pane on desktop, without touching the URL", async () => {
    setViewport(true);
    renderFeed();

    expect(screen.getByRole("heading", { level: 2, name: "Backend Intern" })).toBeInTheDocument();
    expect(link(/Backend Intern/)).toHaveAttribute("aria-current", "true");
    await waitFor(() => expect(jobsApi.get).toHaveBeenCalledWith("j-1"));
    expect(await screen.findByRole("heading", { name: "About Datadog" })).toBeInTheDocument();
    expect(window.location.search).toBe("");
  });

  it("doesn't preselect or fetch details on mobile", () => {
    renderFeed();
    expect(link(/Backend Intern/)).not.toHaveAttribute("aria-current");
    expect(jobsApi.get).not.toHaveBeenCalled();
  });

  it("opens a job in place with a history entry", async () => {
    setViewport(true);
    renderFeed();

    await userEvent.setup().click(link(/Frontend Intern/));

    expect(pushSpy).toHaveBeenCalled();
    expect(search().get("jobId")).toBe("j-2");
    expect(link(/Frontend Intern/)).toHaveAttribute("aria-current", "true");
    expect(link(/Backend Intern/)).not.toHaveAttribute("aria-current");
    expect(screen.getByRole("heading", { level: 2, name: "Frontend Intern" })).toBeInTheDocument();
  });

  it("gives each row a real link and leaves modified clicks to the browser", () => {
    renderFeed();
    const row = link(/Frontend Intern/);
    expect(row).toHaveAttribute("href", "/jobs?jobId=j-2");

    fireEvent.click(row, { ctrlKey: true });
    expect(pushSpy).not.toHaveBeenCalled();
  });

  it("moves focus to the job title on mobile and goes Back to the list", async () => {
    const back = vi.spyOn(window.history, "back").mockImplementation(() => {
      realReplace(null, "", "/jobs");
      window.dispatchEvent(new PopStateEvent("popstate"));
    });
    renderFeed();
    const user = userEvent.setup();

    await user.click(link(/Frontend Intern/));
    const title = screen.getByRole("heading", { level: 2, name: "Frontend Intern" });
    await waitFor(() => expect(title).toHaveFocus());

    await user.click(screen.getByRole("button", { name: /back to results/i }));
    expect(back).toHaveBeenCalled();
    expect(window.location.search).toBe("");
    await waitFor(() => expect(link(/Frontend Intern/)).toHaveFocus());
  });

  it("removes the job from the URL on Back from a deep link (nothing to go back to)", async () => {
    realReplace(null, "", "/jobs?jobId=j-1");
    const back = vi.spyOn(window.history, "back");
    renderFeed();

    await userEvent.setup().click(screen.getByRole("button", { name: /back to results/i }));

    expect(back).not.toHaveBeenCalled();
    expect(window.location.search).toBe("");
  });

  it("says so when a linked job no longer exists", async () => {
    realReplace(null, "", "/jobs?jobId=gone");
    vi.mocked(jobsApi.get).mockRejectedValue(new Error("404"));
    renderFeed();

    expect(await screen.findByText("This job isn't available")).toBeInTheDocument();
  });
});

describe("JobFeed keyboard", () => {
  it("puts one row in the tab order and moves between rows with arrow keys", async () => {
    renderFeed({
      data: feed({
        items: [item("j-1", "Backend Intern", "Datadog"), item("j-2", "Frontend Intern", "Vercel"), item("j-3", "Data Intern", "Snowflake")],
        total: 3,
      }),
    });
    const rows = within(results()).getAllByRole("link");
    expect(rows.map((r) => r.tabIndex)).toEqual([0, -1, -1]);

    const user = userEvent.setup();
    rows[0].focus();
    await user.keyboard("{ArrowDown}");
    expect(rows[1]).toHaveFocus();
    await user.keyboard("{End}");
    expect(rows[2]).toHaveFocus();
    await user.keyboard("{ArrowDown}");
    expect(rows[2]).toHaveFocus();
    await user.keyboard("{Home}");
    expect(rows[0]).toHaveFocus();
    await user.keyboard("{ArrowUp}");
    expect(rows[0]).toHaveFocus();
  });

  it("focuses the job title when a row is opened with Enter on desktop", async () => {
    setViewport(true);
    renderFeed();
    const user = userEvent.setup();

    link(/Frontend Intern/).focus();
    await user.keyboard("{Enter}");

    const title = screen.getByRole("heading", { level: 2, name: "Frontend Intern" });
    await waitFor(() => expect(title).toHaveFocus());
  });

  it("leaves focus on the list when a row is clicked with the mouse on desktop", async () => {
    setViewport(true);
    renderFeed();

    await userEvent.setup().click(link(/Frontend Intern/));
    expect(screen.getByRole("heading", { level: 2, name: "Frontend Intern" })).not.toHaveFocus();
  });
});
