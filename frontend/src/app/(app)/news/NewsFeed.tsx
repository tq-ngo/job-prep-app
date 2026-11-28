"use client";

import { useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Newspaper } from "lucide-react";
import { newsApi, type NewsArticle, type NewsEvent } from "@/lib/api";
import { useNewsAlerts } from "@/hooks/useNewsAlerts";
import Alert from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import { cn } from "@/components/ui/cn";
import EmptyState from "@/components/ui/EmptyState";
import Skeleton, { SkeletonGroup } from "@/components/ui/Skeleton";
import AddArticleForm from "@/components/news/AddArticleForm";
import ArticleCard from "@/components/news/ArticleCard";

export default function NewsFeed({ initialData, initialDataUpdatedAt }: { initialData?: NewsArticle[]; initialDataUpdatedAt?: number }) {
  const queryClient = useQueryClient();

  const { data: articles, isLoading, isError, refetch } = useQuery({
    queryKey: ["news"],
    queryFn: newsApi.list,
    // Seeded by the server render, so the first paint already has today's articles.
    initialData,
    initialDataUpdatedAt,
    staleTime: 60_000,
    // Poll every 5s while any article is still waiting on background AI enrichment.
    refetchInterval: (query) =>
      query.state.data?.some((article) => !article.enriched_at) ? 5000 : false,
  });

  const { connected: sseConnected } = useNewsAlerts({
    onEvent: useCallback(
      (event: NewsEvent) => {
        if (event.kind === "pruned") {
          queryClient.invalidateQueries({ queryKey: ["news"] });
          return;
        }
        if (event.id && (event.kind === "created" || event.kind === "summarized")) {
          queryClient.setQueryData<NewsArticle[]>(["news"], (old) => {
            if (!old) return old;
            const incoming: NewsArticle = {
              id: event.id!,
              title: event.title ?? null,
              url: event.url ?? "",
              source_domain: event.source_domain ?? "",
              published_at: event.published_at ?? null,
              scraped_at: event.scraped_at ?? new Date().toISOString(),
              summary: event.summary ?? null,
              categories: event.categories ?? null,
              tags: event.tags ?? null,
              enriched_at: event.enriched_at ?? null,
            };
            const exists = old.some((a) => a.id === incoming.id);
            if (exists) {
              return old.map((a) => (a.id === incoming.id ? { ...a, ...incoming } : a));
            }
            return [incoming, ...old];
          });
          queryClient.invalidateQueries({ queryKey: ["news"] });
        }
      },
      [queryClient],
    ),
  });

  const count = articles?.length ?? 0;

  return (
    <div className="bg-surface text-on-surface font-sans pt-6 pb-16">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-wrap gap-3 justify-between items-center mb-6 border-b border-outline-variant pb-4">
          <div>
            <h1 className="text-headline-medium font-semibold text-on-surface tracking-tight">Tech News Radar</h1>
            <p className="font-mono text-label-small text-on-surface-variant mt-1 tabular-nums">
              {count > 0 ? `${count} article${count !== 1 ? "s" : ""} · Today's Google tech news` : "Today's Google tech news"}
            </p>
          </div>
          <span
            className="inline-flex items-center gap-1.5 font-mono text-label-small px-2.5 py-0.5 rounded-full bg-surface-container-low border border-outline-variant text-on-surface-variant select-none"
            title={sseConnected ? "Live news updates connected" : "Live news updates disconnected"}
          >
            <span aria-hidden="true" className={cn("w-1.5 h-1.5 rounded-full", sseConnected ? "bg-primary" : "bg-outline-variant")} />
            <span>{sseConnected ? "Live" : "Offline"}</span>
          </span>
        </div>

        <AddArticleForm />

        {isLoading ? (
          <SkeletonGroup label="Loading articles" className="space-y-6">
            {[1, 2, 3].map((i) => (
              <Card key={i} tone="filled" className="h-32 flex flex-col justify-center">
                <Skeleton className="h-3 w-24 mb-4" />
                <Skeleton className="h-6 w-3/4 mb-3" />
                <Skeleton className="h-4 w-full max-w-2xl" />
              </Card>
            ))}
          </SkeletonGroup>
        ) : isError && !articles ? (
          <Alert
            variant="error"
            action={
              <Button variant="outlined" size="sm" onClick={() => refetch()}>
                Retry
              </Button>
            }
          >
            Couldn&apos;t load the news radar. Check your connection and try again.
          </Alert>
        ) : count === 0 ? (
          <EmptyState
            icon={<Newspaper size={20} strokeWidth={1.5} />}
            title="No articles yet today"
            description="Today's Google tech news updates automatically, or paste any article URL above to summarize it now."
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
