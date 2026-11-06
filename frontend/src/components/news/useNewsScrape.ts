"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiErrorMessage } from "@/lib/errors";
import { useScrapePolling } from "@/hooks/useScrapePolling";

interface Options {
  /** Status shown once the task is queued, until it reports progress. */
  queuedMessage: string;
  /** Prefix for a failure, e.g. "Couldn't analyze that article." */
  failureMessage: string;
}

/**
 * One news scrape: start it, follow its task, refresh the feed when it's
 * done. Each caller gets its own state. The page used to share one status
 * line between the URL analyzer and the LinkedIn refresh, so either
 * finishing cleared the other's message.
 */
export function useNewsScrape<TArg>(start: (arg: TArg) => Promise<{ task_id?: string }>, { queuedMessage, failureMessage }: Options) {
  const queryClient = useQueryClient();
  const [taskId, setTaskId] = useState<string | null>(null);
  const [progress, setProgress] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const finish = () => {
    setTaskId(null);
    setProgress(null);
    queryClient.invalidateQueries({ queryKey: ["news"] });
  };

  useScrapePolling(taskId, {
    onSuccess: finish,
    onProgress: (_, message) => setProgress(message || queuedMessage),
    onError: (message) => {
      setTaskId(null);
      setProgress(null);
      setError(`${failureMessage} ${message}`);
    },
  });

  const mutation = useMutation({
    mutationFn: start,
    onMutate: () => setError(null),
    onSuccess: (data) => {
      if (data?.task_id) {
        setTaskId(data.task_id);
        setProgress(queuedMessage);
      } else {
        finish();
      }
    },
    // e.g. a 400 from the SSRF guard, whose detail says why the URL was refused.
    onError: (err) => setError(apiErrorMessage(err, { fallback: `${failureMessage} Try again in a moment.` })),
  });

  return {
    run: mutation.mutateAsync,
    busy: mutation.isPending || !!taskId,
    /** What the task is doing now, while busy. */
    progress: mutation.isPending ? null : progress,
    error,
    dismissError: () => setError(null),
  };
}
