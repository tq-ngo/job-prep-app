"use client";

import { useEffect } from "react";
import { AlertCircle } from "lucide-react";
import { Button, ButtonLink } from "@/components/ui/Button";

export default function AppRouteError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("App route error:", error);
  }, [error]);

  return (
    <div className="max-w-app mx-auto px-4 sm:px-6 py-16 flex justify-center">
      <div className="w-full max-w-md rounded-xl border border-outline-variant bg-surface-container-low p-6 text-center">
        <div className="w-10 h-10 rounded-full bg-error-container text-on-error-container mx-auto flex items-center justify-center mb-4">
          <AlertCircle size={18} strokeWidth={1.5} aria-hidden="true" />
        </div>
        <h1 className="text-title-large font-semibold text-on-surface">Something went wrong</h1>
        <p className="mt-2 text-body-medium text-on-surface-variant">
          We hit an unexpected error loading this view. You can retry now or return to the job board.
        </p>
        <div className="mt-6 flex items-center justify-center gap-3">
          <Button variant="filled" onClick={reset}>
            Try again
          </Button>
          <ButtonLink href="/jobs" variant="outlined">
            Go to jobs
          </ButtonLink>
        </div>
      </div>
    </div>
  );
}
