"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { newsApi } from "@/lib/api";
import { useState } from "react";
import { ExternalLink, Radio } from "lucide-react";

export default function NewsPage() {
  const queryClient = useQueryClient();
  const [scrapeUrl, setScrapeUrl] = useState("");

  const { data: articles, isLoading } = useQuery({
    queryKey: ["news"],
    queryFn: newsApi.list,
  });

  const { mutate: triggerScrape, isPending } = useMutation({
    mutationFn: (url: string) => newsApi.triggerScrape(url),
    onSuccess: () => {
      setScrapeUrl("");
      // Poll for the new article instead of blindly waiting
      let attempts = 0;
      const poll = () => {
        if (attempts >= 10) return; // give up after ~20s
        attempts++;
        setTimeout(() => {
          queryClient.invalidateQueries({ queryKey: ["news"] });
          poll();
        }, 2000);
      };
      poll();
    }
  });

  const handleScrape = (e: React.FormEvent) => {
    e.preventDefault();
    if (scrapeUrl) triggerScrape(scrapeUrl);
  };

  return (
    <div className="min-h-screen bg-background text-foreground font-sans pt-12 pb-24">
      <div className="max-w-4xl mx-auto px-8 lg:px-12">
        
        <div className="flex justify-between items-end mb-12 border-b border-slate-soft pb-8">
          <div>
            <h1 className="text-3xl font-serif font-medium text-slate-ink tracking-tight">
              Tech News Radar
            </h1>
            <p className="font-mono text-xs text-slate-ink/60 mt-3 uppercase tracking-widest">
              AI-summarized insights from across the industry
            </p>
          </div>
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
              disabled={isPending}
              className="bg-spruce-green hover:bg-spruce-green-hover disabled:bg-slate-soft disabled:text-slate-ink/50 text-warm-ivory px-6 py-3 rounded font-sans font-medium transition-colors text-sm border border-transparent disabled:border-slate-soft"
            >
              {isPending ? "Analyzing..." : "Analyze"}
            </button>
          </form>
        </div>

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
                <div className="flex gap-3 mb-4">
                  <span className="font-mono text-[11px] font-medium uppercase tracking-wider text-amber-clay">
                    {article.source_domain}
                  </span>
                  {article.categories?.map(cat => (
                    <span key={cat} className="font-mono text-[11px] font-medium uppercase tracking-wider text-spruce-green/70">
                      • {cat}
                    </span>
                  ))}
                </div>
                <h3 className="text-xl font-serif font-medium text-slate-ink group-hover:text-spruce-green transition-colors mb-3 flex items-start gap-2">
                  {article.title} <ExternalLink size={14} className="opacity-0 group-hover:opacity-100 transition-opacity mt-1 shrink-0 text-spruce-green" />
                </h3>
                <p className="font-sans text-sm text-slate-ink/80 leading-relaxed line-clamp-3">
                  {article.summary || "No summary available."}
                </p>
              </a>
            ))}
            {(!articles || articles.length === 0) && (
              <div className="text-center py-24 font-serif text-slate-ink/60">
                Radar is empty. Submit a URL above to analyze an article.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
