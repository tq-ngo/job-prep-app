"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { newsApi } from "@/lib/api";
import { useState } from "react";
import { ExternalLink, Radio, Loader2, RefreshCw, Clock, Tag } from "lucide-react";
import { useScrapePolling } from "@/hooks/useScrapePolling";

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
    <div className="min-h-screen bg-background text-foreground font-sans pt-12 pb-24">
      <div className="max-w-4xl mx-auto px-8 lg:px-12">
        
        <div className="flex justify-between items-end mb-12 border-b border-slate-soft pb-8">
          <div>
            <h1 className="text-3xl font-serif font-medium text-slate-ink tracking-tight">
              Tech News Radar
            </h1>
            <p className="font-mono text-xs text-slate-ink/60 mt-3 uppercase tracking-widest">
              {articles && articles.length > 0
                ? `${articles.length} article${articles.length !== 1 ? "s" : ""} · AI-summarized insights`
                : "AI-summarized insights from across the industry"
              }
            </p>
          </div>
          <button
            onClick={() => triggerLinkedInRefresh()}
            disabled={isBusy}
            className="flex items-center gap-2 bg-spruce-green hover:bg-spruce-green-hover disabled:bg-slate-soft disabled:text-slate-ink/50 text-warm-ivory px-5 py-2.5 rounded font-sans font-medium transition-colors text-sm border border-transparent disabled:border-slate-soft"
          >
            {(isRefreshing || refreshTaskId) ? (
              <>
                <Loader2 size={14} className="animate-spin" /> Fetching...
              </>
            ) : (
              <>
                <RefreshCw size={14} /> Refresh News
              </>
            )}
          </button>
        </div>

        {/* Scrape new article */}
        <div className="bg-neutral-soft border border-slate-soft rounded p-6 mb-12">
          <h3 className="text-sm font-sans font-medium text-slate-ink mb-4 flex items-center gap-2">
            <Radio size={16} className="text-spruce-green" /> Add Article to Radar
          </h3>
          <form onSubmit={handleScrape} className="flex gap-3">
            <input
              type="url"
              required
              value={scrapeUrl}
              onChange={(e) => setScrapeUrl(e.target.value)}
              placeholder="https://techcrunch.com/article..."
              className="flex-1 bg-background border border-slate-soft text-slate-ink px-4 py-3 rounded focus:outline-none focus:ring-1 focus:ring-spruce-green focus:border-spruce-green text-sm placeholder:text-slate-ink/40 transition-all font-sans"
            />
            <button 
              type="submit" 
              disabled={isBusy}
              className="bg-spruce-green hover:bg-spruce-green-hover disabled:bg-slate-soft disabled:text-slate-ink/50 text-warm-ivory px-6 py-3 rounded font-sans font-medium transition-colors text-sm border border-transparent disabled:border-slate-soft flex items-center gap-2"
            >
              {(isPending || taskId) ? (
                <>
                  <Loader2 size={16} className="animate-spin" /> Analyzing...
                </>
              ) : (
                "Analyze"
              )}
            </button>
          </form>
        </div>

        {statusMsg && (
          <div className="bg-spruce-green/10 border border-spruce-green/30 text-spruce-green px-4 py-3 rounded mb-8 font-mono text-xs flex items-center gap-2 animate-pulse">
            <Loader2 size={14} className="animate-spin" />
            {statusMsg}
          </div>
        )}

        {/* Articles Feed */}
        {isLoading ? (
          <div className="space-y-6">
            {[1,2,3].map(i => (
              <div key={i} className="h-32 bg-neutral-soft rounded border border-slate-soft animate-pulse flex flex-col justify-center px-6">
                <div className="h-3 bg-slate-soft/70 rounded w-24 mb-4"></div>
                <div className="h-6 bg-slate-soft rounded w-3/4 mb-3"></div>
                <div className="h-4 bg-slate-soft/50 rounded w-full max-w-2xl"></div>
              </div>
            ))}
          </div>
        ) : (
          <div className="space-y-6">
            {articles?.map((article) => (
              <a 
                href={article.url} 
                target="_blank" 
                rel="noreferrer"
                key={article.id} 
                className="block bg-background border border-slate-soft p-8 rounded hover:bg-neutral-soft transition-colors duration-200 group"
              >
                {/* Source domain + categories + date */}
                <div className="flex items-center gap-3 mb-4 flex-wrap">
                  <span className="font-mono text-[11px] font-medium uppercase tracking-wider text-amber-clay">
                    {article.source_domain}
                  </span>
                  {article.categories?.map(cat => (
                    <span key={cat} className="font-mono text-[11px] font-medium uppercase tracking-wider text-spruce-green/70">
                      • {cat}
                    </span>
                  ))}
                  {article.published_at && (
                    <span className="ml-auto font-mono text-[11px] text-slate-ink/40 flex items-center gap-1">
                      <Clock size={10} />
                      {new Date(article.published_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
                    </span>
                  )}
                </div>

                {/* Title */}
                <h3 className="text-xl font-serif font-medium text-slate-ink group-hover:text-spruce-green transition-colors mb-3 flex items-start gap-2">
                  {article.title} <ExternalLink size={14} className="opacity-0 group-hover:opacity-100 transition-opacity mt-1 shrink-0 text-spruce-green" />
                </h3>

                {/* Summary */}
                <p className="font-sans text-sm text-slate-ink/80 leading-relaxed line-clamp-3">
                  {article.summary || "No summary available."}
                </p>

                {/* Tags + analyzed time */}
                <div className="flex items-center gap-2 mt-4 flex-wrap">
                  {article.tags?.map(tag => (
                    <span key={tag} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-slate-soft/50 text-slate-ink/60 font-mono text-[10px] uppercase tracking-wider">
                      <Tag size={8} /> {tag}
                    </span>
                  ))}
                  {article.scraped_at && (
                    <span className="ml-auto font-mono text-[10px] text-slate-ink/30">
                      Analyzed {timeAgo(article.scraped_at)}
                    </span>
                  )}
                </div>
              </a>
            ))}
            {(!articles || articles.length === 0) && (
              <div className="text-center py-24">
                <p className="font-serif text-slate-ink/60 mb-4">
                  Radar is empty.
                </p>
                <p className="font-sans text-sm text-slate-ink/40">
                  Click <strong className="text-spruce-green">Refresh News</strong> to fetch today&apos;s LinkedIn headlines, or paste a URL above to analyze any article.
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
