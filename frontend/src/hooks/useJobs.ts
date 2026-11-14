import { keepPreviousData, useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { JobListResponse, JobSummary, jobsApi } from "@/lib/api";

export interface JobListParams {
  page?: number;
  page_size?: number;
  is_remote?: boolean;
  source?: string;
  q?: string;
  category?: string;
  work_type?: string;
  sponsorship?: string;
  skill?: string;
  sort_by?: string;
}

const JOBS_STALE_TIME = 1000 * 60 * 5;

export function useJobs(
  params: JobListParams,
  options: { initialData?: JobListResponse; initialDataUpdatedAt?: number } = {},
) {
  return useQuery({
    queryKey: ["jobs", params],
    queryFn: () => jobsApi.list(params),
    staleTime: JOBS_STALE_TIME,
    // Seed the cache with the server-rendered page. Without this the query
    // started empty, `isLoading` replaced the SSR rows with skeletons, and
    // the same page was fetched a second time from the browser.
    initialData: options.initialData,
    initialDataUpdatedAt: options.initialDataUpdatedAt,
    // Keep showing the current page while the next page or filter loads,
    // instead of flashing the list back to skeletons on every change.
    placeholderData: keepPreviousData,
  });
}

export const jobQueryKey = (id: string) => ["job", id] as const;

/**
 * Full job (with description) for the detail pane. The feed row is shown as
 * placeholder data, so the header and metadata render instantly while the
 * description loads.
 */
export function useJob(id: string | null, placeholder?: JobSummary) {
  return useQuery({
    queryKey: jobQueryKey(id ?? ""),
    queryFn: () => jobsApi.get(id!),
    enabled: !!id,
    staleTime: JOBS_STALE_TIME,
    placeholderData: placeholder ? { ...placeholder, description: null } : undefined,
  });
}

export function usePrefetchJob() {
  const queryClient = useQueryClient();
  return (id: string) =>
    queryClient.prefetchQuery({
      queryKey: jobQueryKey(id),
      queryFn: () => jobsApi.get(id),
      staleTime: JOBS_STALE_TIME,
    });
}

/**
 * Starts a scrape. It doesn't refresh the list: success only means the task
 * was queued, so refetching now returned the same rows. The caller polls
 * the task and invalidates ["jobs"] when it finishes.
 */
export function useTriggerScrape() {
  return useMutation({ mutationFn: jobsApi.triggerScrape });
}
