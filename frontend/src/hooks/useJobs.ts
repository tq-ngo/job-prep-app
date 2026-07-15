import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { jobsApi } from "@/lib/api";

export function useJobs(params: {
  page?: number;
  page_size?: number;
  is_remote?: boolean;
  source?: string;
  q?: string;
  category?: string;
}) {
  return useQuery({
    queryKey: ["jobs", params],
    queryFn: () => jobsApi.list(params),
    staleTime: 1000 * 60 * 5,
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