import { renderHook, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useJobs, useJob, usePrefetchJob, useTriggerScrape, jobQueryKey } from "@/hooks/useJobs";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { jobsApi, JobListResponse, Job, JobSummary } from "@/lib/api";

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
  return {
    queryClient,
    wrapper: ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    ),
  };
}

describe("Jobs Hooks (src/hooks/useJobs.ts)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  describe("useJobs", () => {
    it("fetches job list successfully", async () => {
      const mockList: JobListResponse = {
        items: [
          {
            id: "job-1",
            title: "Frontend Intern",
            company: "Figma",
            location: "San Francisco, CA",
            source: "github",
            apply_url: "https://figma.com",
            skills: ["React"],
            salary_min: 50,
            salary_max: 60,
            salary_currency: "USD",
            is_remote: true,
            posted_at: "2026-03-01T00:00:00Z",
            scraped_at: "2026-03-01T00:00:00Z",
          },
        ],
        total: 1,
        page: 1,
        page_size: 30,
        pages: 1,
      };

      vi.spyOn(jobsApi, "list").mockResolvedValueOnce(mockList);
      const { wrapper } = createWrapper();

      const { result } = renderHook(() => useJobs({ page: 1 }), { wrapper });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data?.items).toHaveLength(1);
      expect(result.current.data?.items[0].company).toBe("Figma");
    });

    it("respects initialData passed from SSR", () => {
      const initialData: JobListResponse = {
        items: [],
        total: 0,
        page: 1,
        page_size: 30,
        pages: 0,
      };

      const { wrapper } = createWrapper();
      const { result } = renderHook(
        () => useJobs({ page: 1 }, { initialData }),
        { wrapper }
      );

      expect(result.current.data).toEqual(initialData);
      expect(result.current.isLoading).toBe(false);
    });
  });

  describe("useJob", () => {
    it("uses placeholder data while description is fetching", async () => {
      const placeholder: JobSummary = {
        id: "job-123",
        title: "SWE Intern",
        company: "Stripe",
        location: "Remote",
        source: "linkedin",
        apply_url: "https://stripe.com",
        skills: ["Ruby"],
        salary_min: null,
        salary_max: null,
        salary_currency: null,
        is_remote: true,
        posted_at: null,
        scraped_at: "2026-03-01T00:00:00Z",
      };

      const fullJob: Job = {
        ...placeholder,
        description: "Full detailed markdown description",
      };

      let resolveJob!: (job: Job) => void;
      const pendingPromise = new Promise<Job>((res) => {
        resolveJob = res;
      });
      vi.spyOn(jobsApi, "get").mockReturnValueOnce(pendingPromise);

      const { wrapper } = createWrapper();
      const { result } = renderHook(
        () => useJob("job-123", placeholder),
        { wrapper }
      );

      // Immediately shows placeholder data with null description
      expect(result.current.data?.title).toBe("SWE Intern");
      expect(result.current.data?.description).toBeNull();

      // Resolve full job
      act(() => {
        resolveJob(fullJob);
      });

      await waitFor(() => expect(result.current.data?.description).toBe("Full detailed markdown description"));
    });
  });

  describe("usePrefetchJob", () => {
    it("prepopulates the job query cache", async () => {
      const fullJob: Job = {
        id: "job-prefetch",
        title: "Platform Intern",
        company: "Airbnb",
        location: "SF",
        source: "github",
        apply_url: "https://airbnb.com",
        description: "Description",
        skills: [],
        salary_min: null,
        salary_max: null,
        salary_currency: null,
        is_remote: false,
        posted_at: null,
        scraped_at: "2026-03-01T00:00:00Z",
      };

      const getSpy = vi.spyOn(jobsApi, "get").mockResolvedValueOnce(fullJob);
      const { queryClient, wrapper } = createWrapper();

      const { result } = renderHook(() => usePrefetchJob(), { wrapper });

      await act(async () => {
        await result.current("job-prefetch");
      });

      expect(getSpy).toHaveBeenCalledWith("job-prefetch");
      const cached = queryClient.getQueryData(jobQueryKey("job-prefetch"));
      expect(cached).toEqual(fullJob);
    });
  });

  describe("useTriggerScrape", () => {
    it("invalidates jobs queries on mutation success", async () => {
      vi.spyOn(jobsApi, "triggerScrape").mockResolvedValueOnce({
        task_id: "task-abc",
        status: "PENDING",
      });

      const { queryClient, wrapper } = createWrapper();
      const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

      const { result } = renderHook(() => useTriggerScrape(), { wrapper });

      await act(async () => {
        await result.current.mutateAsync("github");
      });

      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["jobs"] });
    });
  });
});

