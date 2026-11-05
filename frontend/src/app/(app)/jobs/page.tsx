import { Suspense } from "react";
import { cookies } from "next/headers";
import { JobListResponse } from "@/lib/api";
import { parseJobFilters, toListParams } from "@/lib/job-filters";
import { INTERNAL_API_URL } from "@/lib/server-api";
import { JobListSkeleton } from "@/components/jobs/JobList";
import JobFeed from "./JobFeed";

type SearchParams = Record<string, string | string[] | undefined>;

export default async function JobsPage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  // Seed the page the URL asks for. This used to always fetch page 1 with no
  // filters, so a reload of ?category=Quant&page=2 rendered the wrong rows
  // and then fetched the right ones from the browser.
  const params = await searchParams;
  const filters = parseJobFilters((k) => {
    const v = params[k];
    return typeof v === "string" ? v : null;
  });

  let initialData: JobListResponse | undefined;
  let initialDataUpdatedAt: number | undefined;
  try {
    const query = new URLSearchParams(
      Object.entries(toListParams(filters)).map(([k, v]) => [k, String(v)]),
    );
    // Forward the caller's cookies: the list is per-user and authenticated,
    // so it must never be fetched anonymously or cached across users.
    const cookieHeader = (await cookies()).toString();
    const res = await fetch(`${INTERNAL_API_URL}/api/v1/jobs/?${query}`, {
      headers: cookieHeader ? { cookie: cookieHeader } : {},
      cache: "no-store",
    });
    if (res.ok) {
      initialData = await res.json();
      // Tells React Query how old the seeded data is, so its staleTime
      // applies from the API response rather than from hydration.
      initialDataUpdatedAt = Date.parse(res.headers.get("date") ?? "") || undefined;
    }
  } catch {
    // Fall back to client-side fetching; JobFeed handles an undefined prop.
  }

  return (
    // useSearchParams in the feed needs a boundary.
    <Suspense fallback={<JobListSkeleton />}>
      <JobFeed initialData={initialData} initialDataUpdatedAt={initialDataUpdatedAt} initialFilters={filters} />
    </Suspense>
  );
}
