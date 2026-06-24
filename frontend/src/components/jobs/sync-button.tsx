"use client";

import { useState, useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { triggerSimplifySync, getSyncStreamUrl } from "@/api/jobs";
import { Button } from "@/components/ui/button";
import { RefreshCw, CheckCircle2, Loader2, AlertCircle } from "lucide-react";

export default function SyncButton() {
  const [taskId, setTaskId] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [message, setMessage] = useState<string>("");
  const queryClient = useQueryClient();

  const syncMutation = useMutation({
    mutationFn: triggerSimplifySync,
    onSuccess: (data) => {
      setTaskId(data.task_id);
      setStatus("PENDING");
      setMessage("Queuing task...");
    },
  });

  useEffect(() => {
    if (!taskId) return;

    const streamUrl = getSyncStreamUrl(taskId);
    const eventSource = new EventSource(streamUrl);

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setStatus(data.status);
      setMessage(data.message);

      if (data.status === "SUCCESS") {
        queryClient.invalidateQueries({ queryKey: ["jobs"] });
        eventSource.close();
        // Clear after 5 seconds
        setTimeout(() => {
          setTaskId(null);
          setStatus(null);
          setMessage("");
        }, 5000);
      } else if (data.status === "FAILURE") {
        eventSource.close();
      }
    };

    eventSource.onerror = (err) => {
      console.error("SSE Error:", err);
      setStatus("FAILURE");
      setMessage("Connection lost. Check background logs.");
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  }, [taskId, queryClient]);

  const isSyncing = !!(syncMutation.isPending || (taskId && status !== "SUCCESS" && status !== "FAILURE"));

  return (
    <div className="flex flex-col items-end gap-2">
      <Button 
        onClick={() => syncMutation.mutate()} 
        disabled={isSyncing}
        variant="outline"
        className="min-w-[140px]"
      >
        {status === "SUCCESS" ? (
          <>
            <CheckCircle2 className="mr-2 h-4 w-4 text-green-500" />
            Sync Complete
          </>
        ) : status === "FAILURE" ? (
          <>
            <AlertCircle className="mr-2 h-4 w-4 text-red-500" />
            Sync Failed
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
      {isSyncing && message && (
        <span className="text-xs text-muted-foreground animate-pulse">
          {message}
        </span>
      )}
      {status === "FAILURE" && message && (
        <span className="text-xs text-red-500 max-w-[200px] text-right">
          {message}
        </span>
      )}
    </div>
  );
}
