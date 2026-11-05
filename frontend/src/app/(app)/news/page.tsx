"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { newsApi } from "@/lib/api";
import { useState } from "react";
import { ExternalLink, Radio, RefreshCw, Clock, Tag, Newspaper } from "lucide-react";
import { useScrapePolling } from "@/hooks/useScrapePolling";
import Alert from "@/components/ui/Alert";
import Badge from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import Card, { cardClasses } from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import Field from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import Skeleton, { SkeletonGroup } from "@/components/ui/Skeleton";
import Spinner from "@/components/ui/Spinner";

function timeAgo(dateStr: string): string {
  const seconds = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export default function NewsPage() {
  const queryClient = useQueryClient();
  const [scrapeUrl, setScrapeUrl] = useState("");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [statusMsg, setStatusMsg] = useState<string>("");
  const [refreshTaskId, setRefreshTaskId] = useState<string | null>(null);

  // Polling for manual URL scrape
  useScrapePolling(
    taskId,
    () => {
      setTaskId(null);
      setStatusMsg("");
      queryClient.invalidateQueries({ queryKey: ["news"] });
    },
    (percent, message) => {
      setStatusMsg(message || "Processing article...");
    }
  );

  // Polling for LinkedIn News refresh
  useScrapePolling(
    refreshTaskId,
    () => {
      setRefreshTaskId(null);
      setStatusMsg("");
      queryClient.invalidateQueries({ queryKey: ["news"] });
    },
    (percent, message) => {
      setStatusMsg(message || "Fetching LinkedIn daily news...");
    }
  );

  const { data: articles, isLoading } = useQuery({
    queryKey: ["news"],
    queryFn: newsApi.list,
  });

  const { mutate: triggerScrape, isPending } = useMutation({
    mutationFn: (url: string) => newsApi.triggerScrape(url),
    onSuccess: (data) => {
      setScrapeUrl("");
      if (data && data.task_id) {
        setTaskId(data.task_id);
        setStatusMsg("Analyzing article content and generating AI summary...");
      } else {
        queryClient.invalidateQueries({ queryKey: ["news"] });
      }
    }
  });

  const { mutate: triggerLinkedInRefresh, isPending: isRefreshing } = useMutation({
    mutationFn: () => newsApi.triggerLinkedInNews(),
    onSuccess: (data) => {
      if (data && data.task_id) {
        setRefreshTaskId(data.task_id);
        setStatusMsg("Fetching LinkedIn daily headlines...");
      }
    }
  });

  const handleScrape = (e: React.FormEvent) => {
    e.preventDefault();
    if (scrapeUrl) triggerScrape(scrapeUrl);
  };

  const isBusy = isPending || !!taskId || isRefreshing || !!refreshTaskId;

  return (
    <div className="min-h-screen bg-background text-foreground font-sans pt-6 pb-16">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        
        <div className="flex justify-between items-center mb-6 border-b border-slate-soft pb-4">
          <div>
            <h1 className="text-2xl font-serif font-medium text-slate-ink tracking-tight">
              Tech News Radar
            </h1>
            <p className="font-mono text-xs text-foreground-muted mt-1 uppercase tracking-wider">
              {articles && articles.length > 0
                ? `${articles.length} article${articles.length !== 1 ? "s" : ""} · AI-summarized insights`
                : "AI-summarized insights from across the industry"
              }
            </p>
          </div>
          <Button
            size="sm"
            onClick={() => triggerLinkedInRefresh()}
            disabled={isBusy}
            loading={isRefreshing || !!refreshTaskId}
            icon={<RefreshCw size={13} aria-hidden="true" />}
          >
            {isRefreshing || refreshTaskId ? "Fetching..." : "Refresh News"}
          </Button>
        </div>

        {/* Scrape new article */}
        <Card as="section" tone="muted" padding="sm" className="mb-8" aria-labelledby="add-article-heading">
          <h2 id="add-article-heading" className="text-xs font-sans font-medium text-slate-ink mb-3 flex items-center gap-2">
            <Radio size={14} aria-hidden="true" className="text-spruce-green" /> Add Article to Radar
          </h2>
          <form onSubmit={handleScrape} className="flex gap-2 items-start">
            <Field label="Article URL" labelVisible={false} className="flex-1">
              <Input
                size="sm"
                type="url"
                required
                value={scrapeUrl}
                onChange={(e) => setScrapeUrl(e.target.value)}
                placeholder="https://techcrunch.com/article..."
              />
            </Field>
            <Button type="submit" size="sm" disabled={isBusy} loading={isPending || !!taskId}>
              {isPending || taskId ? "Analyzing..." : "Analyze"}
            </Button>
          </form>
        </Card>

        {statusMsg && (
          <Alert icon={<Spinner />} className="mb-8">
            {statusMsg}
          </Alert>
        )}

        {/* Articles Feed */}
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
        ) : (
          <div className="space-y-6">
            {articles?.map((article) => (
              <a 
                href={article.url} 
                target="_blank" 
                rel="noreferrer"
                key={article.id} 
                className={cardClasses({ padding: "lg", className: "block hover:bg-neutral-soft transition-colors duration-200 group" })}
              >
                {/* Source domain + categories + date */}
                <div className="flex items-center gap-3 mb-4 flex-wrap">
                  <span className="font-mono text-2xs font-medium uppercase tracking-wider text-amber-clay">
                    {article.source_domain}
                  </span>
                  {article.categories?.map(cat => (
                    <span key={cat} className="font-mono text-2xs font-medium uppercase tracking-wider text-spruce-green">
                      • {cat}
                    </span>
                  ))}
                  {article.published_at && (
                    <span className="ml-auto font-mono text-2xs text-foreground-subtle flex items-center gap-1">
                      <Clock size={10} />
                      {new Date(article.published_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
                    </span>
                  )}
                </div>

                {/* Title */}
                <h2 className="text-xl font-serif font-medium text-slate-ink group-hover:text-spruce-green transition-colors mb-3 flex items-start gap-2">
                  {article.title} <ExternalLink size={14} className="opacity-0 group-hover:opacity-100 transition-opacity mt-1 shrink-0 text-spruce-green" />
                </h2>

                {/* Summary */}
                <p className="font-sans text-sm text-foreground-muted leading-relaxed line-clamp-3">
                  {article.summary || "No summary available."}
                </p>
                {!article.enriched_at && (
                  <p className="mt-2 inline-flex items-center gap-1.5 font-mono text-2xs uppercase tracking-wider text-foreground-subtle">
                    <Spinner size={11} /> AI summary pending
                  </p>
                )}

                {/* Tags + analyzed time */}
                <div className="flex items-center gap-2 mt-4 flex-wrap">
                  {article.tags?.map(tag => (
                    <Badge key={tag}>
                      <Tag size={8} aria-hidden="true" /> {tag}
                    </Badge>
                  ))}
                  {article.scraped_at && (
                    <span className="ml-auto font-mono text-2xs text-foreground-subtle">
                      Analyzed {timeAgo(article.scraped_at)}
                    </span>
                  )}
                </div>
              </a>
            ))}
            {(!articles || articles.length === 0) && (
              <EmptyState
                icon={<Newspaper size={22} />}
                title="Radar is empty."
                description={
                  <>
                    Click <strong className="text-spruce-green">Refresh News</strong> to fetch today&apos;s LinkedIn headlines, or paste a URL above to analyze any article.
                  </>
                }
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
