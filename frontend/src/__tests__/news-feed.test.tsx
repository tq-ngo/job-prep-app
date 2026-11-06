import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import NewsFeed from "@/app/(app)/news/NewsFeed";
import { newsApi, tasksApi, type NewsArticle } from "@/lib/api";

const article: NewsArticle = {
  id: "a-1",
  title: "Chipmakers expand AI capacity",
  url: "https://news.example/chips",
  source_domain: "news.example",
  published_at: "2026-03-01T00:00:00Z",
  scraped_at: "2026-03-01T00:00:00Z",
  summary: "Datacenter investment keeps climbing.",
  categories: ["Hardware"],
  tags: ["gpu"],
  enriched_at: "2026-03-01T00:00:00Z",
};

function renderFeed(initialData: NewsArticle[] | null = [article]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <NewsFeed initialData={initialData ?? undefined} />
    </QueryClientProvider>,
  );
  return userEvent.setup();
}

beforeEach(() => {
  vi.spyOn(newsApi, "list").mockResolvedValue([article]);
});
afterEach(() => {
  vi.restoreAllMocks();
});

describe("NewsFeed", () => {
  it("renders the server-seeded articles without refetching", () => {
    renderFeed();
    expect(screen.getByRole("link", { name: /chipmakers expand ai capacity/i })).toHaveAttribute("href", article.url);
    expect(newsApi.list).not.toHaveBeenCalled();
  });

  it("shows an error with Retry, not 'Radar is empty', when the list can't load", async () => {
    vi.mocked(newsApi.list).mockRejectedValue(new Error("offline"));
    const user = renderFeed(null);

    expect(await screen.findByText(/couldn't load the news radar/i)).toBeInTheDocument();
    expect(screen.queryByText("Radar is empty.")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(newsApi.list).toHaveBeenCalledTimes(2);
  });

  it("shows why a URL was refused and keeps it for editing", async () => {
    vi.spyOn(newsApi, "triggerScrape").mockRejectedValue({
      response: { status: 400, data: { detail: "URL resolves to a non-public address" } },
    });
    const user = renderFeed();
    const input = screen.getByRole("textbox", { name: "Article URL" });

    await user.type(input, "http://169.254.169.254/latest");
    await user.click(screen.getByRole("button", { name: "Analyze" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("non-public address");
    expect(input).toHaveValue("http://169.254.169.254/latest");
    expect(screen.getByRole("button", { name: "Analyze" })).toBeEnabled();
  });

  it("tracks the two scrapes separately", async () => {
    vi.spyOn(newsApi, "triggerLinkedInNews").mockResolvedValue({ task_id: "t-linkedin", status: "accepted" });
    vi.spyOn(newsApi, "triggerScrape").mockResolvedValue({ task_id: "t-url" });
    vi.spyOn(tasksApi, "getStatus").mockImplementation(async (id) =>
      id === "t-url" ? { status: "SUCCESS", result: null, error: null } : { status: "PENDING", result: null, error: null },
    );
    const user = renderFeed();

    await user.click(screen.getByRole("button", { name: "Refresh News" }));
    expect(await screen.findByText(/fetching linkedin daily headlines/i)).toBeInTheDocument();

    await user.type(screen.getByRole("textbox", { name: "Article URL" }), "https://news.example/new");
    await user.click(screen.getByRole("button", { name: "Analyze" }));

    // The URL task finished; the LinkedIn one is still running and still says so.
    expect(await screen.findByRole("button", { name: "Analyze" })).toBeEnabled();
    expect(screen.getByText(/fetching linkedin daily headlines/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Fetching…" })).toBeDisabled();
  });

  it("reports a failed refresh and resets the button", async () => {
    vi.spyOn(newsApi, "triggerLinkedInNews").mockResolvedValue({ task_id: "t-1", status: "accepted" });
    vi.spyOn(tasksApi, "getStatus").mockResolvedValue({ status: "FAILURE", result: null, error: "LinkedIn blocked the request" });
    const user = renderFeed();

    await user.click(screen.getByRole("button", { name: "Refresh News" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Couldn't fetch LinkedIn headlines. The task failed: LinkedIn blocked the request");
    expect(screen.getByRole("button", { name: "Refresh News" })).toBeEnabled();
    await user.click(within(alert).getByRole("button", { name: "Dismiss" }));
    await act(async () => {});
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
