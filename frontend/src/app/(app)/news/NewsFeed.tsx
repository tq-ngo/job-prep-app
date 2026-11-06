"use client";

import { useQuery } from "@tanstack/react-query";
import { Newspaper, RefreshCw } from "lucide-react";
import { newsApi, type NewsArticle } from "@/lib/api";
import Alert from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import Skeleton, { SkeletonGroup } from "@/components/ui/Skeleton";
import Spinner from "@/components/ui/Spinner";
import AddArticleForm from "@/components/news/AddArticleForm";
import ArticleCard from "@/components/news/ArticleCard";
import { useNewsScrape } from "@/components/news/useNewsScrape";

export default function NewsFeed({ initialData, initialDataUpdatedAt }: { initialData?: NewsArticle[]; initialDataUpdatedAt?: number }) {
  const { data: articles, isLoading, isError, refetch } = useQuery({
    queryKey: ["news"],
    queryFn: newsApi.list,
    // Seeded by the server render, so the first paint already has articles.
    initialData,
    initialDataUpdatedAt,
    staleTime: 60_000,
  });

  const linkedin = useNewsScrape(() => newsApi.triggerLinkedInNews(), {
    queuedMessage: "Fetching LinkedIn daily headlines…",
    failureMessage: "Couldn't fetch LinkedIn headlines.",
  });

  const count = articles?.length ?? 0;

  return (
    <div className="bg-background text-foreground font-sans pt-6 pb-16">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-wrap gap-3 justify-between items-center mb-6 border-b border-slate-soft pb-4">
          <div>
            <h1 className="text-2xl font-serif font-medium text-slate-ink tracking-tight">Tech News Radar</h1>
            <p className="font-mono text-xs text-foreground-muted mt-1 uppercase tracking-wider">
              {count > 0 ? `${count} article${count !== 1 ? "s" : ""} · AI-summarized insights` : "AI-summarized insights from across the industry"}
            </p>
          </div>
          <Button
            size="sm"
            onClick={() => linkedin.run(undefined).catch(() => {})}
            loading={linkedin.busy}
            icon={<RefreshCw size={13} aria-hidden="true" />}
          >
            {linkedin.busy ? "Fetching…" : "Refresh News"}
          </Button>
        </div>

        {linkedin.progress && (
          <Alert icon={<Spinner />} className="mb-6">
            {linkedin.progress}
          </Alert>
        )}
        {linkedin.error && (
          <Alert
            variant="error"
            className="mb-6"
            action={
              <Button variant="ghost" size="sm" onClick={linkedin.dismissError}>
                Dismiss
              </Button>
            }
          >
            {linkedin.error}
          </Alert>
        )}

        <AddArticleForm />

        {isLoading ? (
          <SkeletonGroup label="Loading articles" className="space-y-6">
            {[1, 2, 3].map((i) => (
              <Card key={i} tone="muted" className="h-32 flex flex-col justify-center">
                <Skeleton className="h-3 w-24 mb-4" />
                <Skeleton className="h-6 w-3/4 mb-3" />
                <Skeleton className="h-4 w-full max-w-2xl" />
              </Card>
            ))}
          </SkeletonGroup>
        ) : isError && !articles ? (
          // Not "Radar is empty": that told people to fetch more news when
          // the real problem was that the list couldn't load at all.
          <Alert
            variant="error"
            action={
              <Button variant="secondary" size="sm" onClick={() => refetch()}>
                Retry
              </Button>
            }
          >
            Couldn&apos;t load the news radar. Check your connection and try again.
          </Alert>
        ) : count === 0 ? (
          <EmptyState
            icon={<Newspaper size={22} />}
            title="Radar is empty."
            description={
              <>
                Click <strong className="text-spruce-green">Refresh News</strong> to fetch today&apos;s LinkedIn headlines, or paste a URL above to analyze any article.
              </>
            }
          />
        ) : (
          <div className="space-y-6">
            {articles!.map((article) => (
              <ArticleCard key={article.id} article={article} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
