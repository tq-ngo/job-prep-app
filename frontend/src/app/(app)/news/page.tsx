import { cookies } from "next/headers";
import type { NewsArticle } from "@/lib/api";
import { INTERNAL_API_URL } from "@/lib/server-api";
import NewsFeed from "./NewsFeed";

/**
 * Server component, like /jobs: the first fetch happens here so the page
 * arrives with articles in it. It used to be a client-only page that
 * rendered skeletons, hydrated, and only then requested the list.
 */
export default async function NewsPage() {
  let initialData: NewsArticle[] | undefined;
  let initialDataUpdatedAt: number | undefined;
  try {
    const cookieHeader = (await cookies()).toString();
    const res = await fetch(`${INTERNAL_API_URL}/api/v1/news/`, {
      headers: cookieHeader ? { cookie: cookieHeader } : {},
      // Per-user (authenticated) data: never cache across requests.
      cache: "no-store",
    });
    if (res.ok) {
      initialData = await res.json();
      initialDataUpdatedAt = Date.parse(res.headers.get("date") ?? "") || undefined;
    }
  } catch {
    // The client fetches instead (and shows an error state if that fails too).
  }
  return <NewsFeed initialData={initialData} initialDataUpdatedAt={initialDataUpdatedAt} />;
}
