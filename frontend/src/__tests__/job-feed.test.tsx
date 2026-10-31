import { render, screen, fireEvent, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import JobFeed from "@/app/(app)/jobs/JobFeed";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { JobEvent, JobListResponse } from "@/lib/api";

const mockPush = vi.fn();
const mockReplace = vi.fn();
let mockSearchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
    replace: mockReplace,
  }),
  usePathname: () => "/jobs",
  useSearchParams: () => mockSearchParams,
}));

let mockJobAlertsHandler: ((event: JobEvent) => void) | undefined;
vi.mock("@/hooks/useJobAlerts", () => ({
  useJobAlerts: ({ onEvent }: { onEvent?: (event: JobEvent) => void } = {}) => {
    mockJobAlertsHandler = onEvent;
    return { connected: true };
  },
}));

vi.mock("@/components/JobDetailsSidebar", () => ({
  default: ({ job, open, onClose }: { job?: { title?: string }; open: boolean; onClose: () => void }) =>
    open ? (
      <div data-testid="mock-drawer">
        <span>{job?.title}</span>
        <button onClick={onClose}>Close</button>
      </div>
    ) : null,
}));

const mockFeedData: JobListResponse = {
  items: [
    {
      id: "j-1",
      title: "Backend Intern",
      company: "Datadog",
      location: "Boston, MA",
      source: "github",
      apply_url: "https://datadog.com",
      skills: ["Go", "Kubernetes"],
      salary_min: 55,
      salary_max: 65,
      salary_currency: "USD",
      is_remote: false,
      posted_at: "2026-03-01T00:00:00Z",
      scraped_at: "2026-03-01T00:00:00Z",
    },
    {
      id: "j-2",
      title: "Frontend Intern",
      company: "Vercel",
      location: "Remote",
      source: "linkedin",
      apply_url: "https://vercel.com",
      skills: ["React", "Next.js"],
      salary_min: 60,
      salary_max: 70,
      salary_currency: "USD",
      is_remote: true,
      posted_at: "2026-03-02T00:00:00Z",
      scraped_at: "2026-03-02T00:00:00Z",
    },
  ],
  total: 2,
  page: 1,
  page_size: 30,
  pages: 1,
};

function renderJobFeed(initialData = mockFeedData) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <JobFeed initialData={initialData} />
    </QueryClientProvider>
  );
}

describe("JobFeed Component (src/app/(app)/jobs/JobFeed.tsx)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSearchParams = new URLSearchParams();
  });

  it("renders job postings from initialData", () => {
    renderJobFeed();

    expect(screen.getByText("Backend Intern")).toBeInTheDocument();
    expect(screen.getByText("Datadog")).toBeInTheDocument();
    expect(screen.getByText("Frontend Intern")).toBeInTheDocument();
    expect(screen.getByText("Vercel")).toBeInTheDocument();
    expect(screen.getByText(/2 roles/i)).toBeInTheDocument();
  });

  it("updates category filter and resets page to 1", () => {
    renderJobFeed();

    const categorySelect = screen.getByLabelText(/Category/i);
    fireEvent.change(categorySelect, { target: { value: "FAANG+" } });

    expect(mockReplace).toHaveBeenCalledWith(
      expect.stringContaining("/jobs"),
      expect.anything()
    );
  });

  it("displays pending new postings banner when SSE 'created' event arrives", () => {
    renderJobFeed();

    expect(screen.queryByText(/new job/i)).not.toBeInTheDocument();

    act(() => {
      mockJobAlertsHandler?.({
        kind: "created",
        id: "j-3",
        title: "Security Intern",
        company: "Cloudflare",
      });
    });

    expect(screen.getByText(/1 new job/i)).toBeInTheDocument();

    act(() => {
      mockJobAlertsHandler?.({
        kind: "created",
        id: "j-4",
        title: "Data Intern",
        company: "Snowflake",
      });
    });

    expect(screen.getByText(/2 new jobs/i)).toBeInTheDocument();
  });

  it("opens job details drawer when a job row is clicked", () => {
    renderJobFeed();

    const jobRow = screen.getByText("Backend Intern").closest("tr, div, button") || screen.getByText("Backend Intern");
    fireEvent.click(jobRow);

    expect(mockPush).toHaveBeenCalledWith(
      expect.stringContaining("jobId=j-1"),
      expect.anything()
    );
  });
});
