import { Suspense } from "react";
import { cookies } from "next/headers";
import { JobListResponse } from "@/lib/api";
import JobFeed from "./JobFeed";

export default async function JobsPage() {
  let initialData: JobListResponse | undefined = undefined;

  try {
    const apiUrl =
      process.env.INTERNAL_API_URL ||
      process.env.NEXT_PUBLIC_API_URL ||
      "http://localhost:8000";

    // Forward the caller's cookies. This fetch previously went out with NO
    // credentials against an endpoint that accepted anonymous callers, so the
    // job data was embedded in the RSC payload and shipped to anyone who
    // requested /jobs — the client-side AuthGuard only blanked the UI long
    // after the bytes had left the server.
    const cookieHeader = (await cookies()).toString();

    const res = await fetch(`${apiUrl}/api/v1/jobs/?page=1&page_size=30`, {
      headers: cookieHeader ? { cookie: cookieHeader } : {},
      // Per-user data must never be cached and shared between users.
      cache: "no-store",
    });
    if (res.ok) {
      initialData = await res.json();
    }
  } catch {
    // Fall back to client-side fetching; JobFeed handles an undefined prop.
  }

  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-background text-foreground-muted flex items-center justify-center font-sans text-xs">
          Loading jobs...
        </div>
      }
    >
      <JobFeed initialData={initialData} />
    </Suspense>
  );
}
