import { JobListResponse } from "@/lib/api";
import JobFeed from "./JobFeed";

export default async function JobsPage() {
  let initialData: JobListResponse | undefined = undefined;
  
  try {
    const apiUrl = process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const res = await fetch(`${apiUrl}/api/v1/jobs/?page=1&page_size=50`, {
      next: { revalidate: 30 }
    });
    if (res.ok) {
      initialData = await res.json();
    }
  } catch (error) {
    console.warn("SSR initial fetch failed, falling back to client-side.");
  }

  return <JobFeed initialData={initialData} />;
}
