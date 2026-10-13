import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { JobListResponse, JobSummary, jobsApi } from "@/lib/api";

export interface JobListParams {
  page?: number;
  page_size?: number;
  is_remote?: boolean;
  source?: string;
  q?: string;
  category?: string;
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
  });
}

export const jobQueryKey = (id: string) => ["job", id] as const;

/**
 * Full job (with description) for the drawer. The feed row is shown as
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

export function useTriggerScrape() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: jobsApi.triggerScrape,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
}
