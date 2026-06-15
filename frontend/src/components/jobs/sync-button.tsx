"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { triggerSimplifySync, getSyncStatus } from "@/api/jobs";
import { Button } from "@/components/ui/button";
import { RefreshCw, CheckCircle2, Loader2 } from "lucide-react";

export default function SyncButton() {
  const [taskId, setTaskId] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const syncMutation = useMutation({
    mutationFn: triggerSimplifySync,
    onSuccess: (data) => {
      setTaskId(data.task_id);
    },
  });

  const { data: statusData } = useQuery({
    queryKey: ["sync-status", taskId],
    queryFn: () => getSyncStatus(taskId!),
    enabled: !!taskId,
    refetchInterval: (query) => {
      const data = query.state.data as any;
      if (data?.status === "SUCCESS" || data?.status === "FAILURE") {
        return false;
      }
      return 3000;
    },
  });

  useEffect(() => {
    if (statusData?.status === "SUCCESS") {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      const timer = setTimeout(() => setTaskId(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [statusData, queryClient]);

  const isSyncing = !!(syncMutation.isPending || (taskId && statusData?.status !== "SUCCESS" && statusData?.status !== "FAILURE"));

  return (
    <Button 
      onClick={() => syncMutation.mutate()} 
      disabled={isSyncing}
      variant="outline"
    >
      {statusData?.status === "SUCCESS" ? (
        <>
          <CheckCircle2 className="mr-2 h-4 w-4 text-green-500" />
          Sync Complete
        </>
      ) : isSyncing ? (
        <>
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          Syncing...
        </>
      ) : (
        <>
          <RefreshCw className="mr-2 h-4 w-4" />
          Sync Simplify
        </>
      )}
    </Button>
  );
}
