"use client";

import { useState, useMemo, useCallback } from "react";
import { useJobs, useTriggerScrape } from "@/hooks/useJobs";
import { Job, JobListResponse } from "@/lib/api";
import JobDetailsSidebar from "@/components/JobDetailsSidebar";
import { Search, ExternalLink, RefreshCw, Briefcase } from "lucide-react";
import { useScrapePolling } from "@/hooks/useScrapePolling";

interface JobFeedProps {
  initialData?: JobListResponse;
}

export default function JobFeed({ initialData }: JobFeedProps) {
  const [page, setPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState("");
  const [category, setCategory] = useState("");
  const [source, setSource] = useState("");
  const [isRemote, setIsRemote] = useState(false);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);

  const { data: jobsResponse, isLoading, refetch } = useJobs({ 
    page, 
    page_size: 50,
    category: category || undefined,
    is_remote: isRemote || undefined,
    source: source || undefined
  });

  const triggerScrape = useTriggerScrape();

  const onScrapeComplete = useCallback(() => {
    setTaskId(null);
    refetch();
  }, [refetch]);

  useScrapePolling(taskId, onScrapeComplete);

  const handleRefreshScrapers = () => {
    triggerScrape.mutate("github", {
      onSuccess: (data) => {
        if (data.task_id) {
          setTaskId(data.task_id);
        } else {
          refetch();
        }
      }
    });
  };

  const isDefaultState = page === 1 && !isRemote && !source && !category;
  const currentData = isDefaultState && !jobsResponse ? initialData : jobsResponse;
  const currentJobs = currentData?.items ?? [];

  const filteredJobs = useMemo(() => {
    if (!searchQuery.trim()) return currentJobs;
    const q = searchQuery.toLowerCase();
    return currentJobs.filter((job) =>
      job.title.toLowerCase().includes(q) ||
      job.company.toLowerCase().includes(q) ||
      (job.location && job.location.toLowerCase().includes(q))
    );
  }, [currentJobs, searchQuery]);

  const isScraping = triggerScrape.isPending || !!taskId;

  return (
    <div className="min-h-screen bg-background text-foreground font-sans">
      {/* Top Header & Filter Bar */}
      <div className="bg-background border-b border-slate-soft pt-12 pb-8">
        <div className="max-w-5xl mx-auto px-8 lg:px-12">
          <div className="flex justify-between items-end mb-8">
            <div>
              <h1 className="text-3xl font-serif font-medium text-slate-ink tracking-tight">Job Board</h1>
              <p className="font-mono text-xs text-slate-ink/60 mt-3 uppercase tracking-widest">
                {currentData ? `${currentData.total} positions tracked` : "Click Refresh to start scraping"}
              </p>
            </div>
            
            <button 
              onClick={handleRefreshScrapers}
              disabled={isScraping}
              className="flex items-center gap-2 bg-spruce-green hover:bg-spruce-green-hover disabled:bg-slate-soft disabled:text-slate-ink/50 text-warm-ivory px-5 py-2.5 rounded font-sans font-medium transition-colors text-sm border border-transparent disabled:border-slate-soft"
            >
              <RefreshCw size={16} className={isScraping ? "animate-spin" : ""} />
              {isScraping ? "Syncing..." : "Refresh Board"}
            </button>
          </div>

          <div className="flex flex-col lg:flex-row gap-4 lg:items-center">
            {/* Search bar */}
            <div className="flex-1 max-w-md relative">
              <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-ink/40" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Filter jobs by keyword..."
                className="w-full pl-10 pr-4 py-2.5 bg-transparent border border-slate-soft rounded focus:outline-none focus:ring-1 focus:ring-spruce-green focus:border-spruce-green text-sm text-slate-ink placeholder:text-slate-ink/40 transition-all font-sans"
              />
              {searchQuery && (
                <button 
                  onClick={() => setSearchQuery("")}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-slate-ink/50 hover:text-slate-ink"
                >
                  Clear
                </button>
              )}
            </div>

            {/* Filter dropdowns */}
            <div className="flex flex-wrap gap-3 items-center lg:ml-auto">
              <select
                value={category}
                onChange={(e) => { setCategory(e.target.value); setPage(1); }}
                className="appearance-none bg-transparent border border-slate-soft hover:border-slate-ink/20 text-slate-ink text-sm font-sans rounded px-4 py-2.5 focus:outline-none focus:ring-1 focus:ring-spruce-green transition-all cursor-pointer"
              >
                <option value="">All Categories</option>
                <option value="FAANG+">FAANG+</option>
                <option value="Quant">Quant</option>
                <option value="Others">Others</option>
              </select>

              <select
                value={source}
                onChange={(e) => { setSource(e.target.value); setPage(1); }}
                className="appearance-none bg-transparent border border-slate-soft hover:border-slate-ink/20 text-slate-ink text-sm font-sans rounded px-4 py-2.5 focus:outline-none focus:ring-1 focus:ring-spruce-green transition-all cursor-pointer"
              >
                <option value="">All Sources</option>
                <option value="github">GitHub</option>
                <option value="linkedin">LinkedIn</option>
              </select>

              <button
                type="button"
                onClick={() => { setIsRemote(!isRemote); setPage(1); }}
                className={`text-sm font-sans font-medium rounded px-4 py-2.5 border transition-all ${
                  isRemote 
                    ? "bg-amber-clay/10 border-amber-clay/40 text-amber-clay" 
                    : "bg-transparent border-slate-soft hover:border-slate-ink/20 text-slate-ink"
                }`}
              >
                Remote
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="max-w-5xl mx-auto px-8 lg:px-12 py-12">
        
        {!isLoading && currentJobs.length === 0 && !searchQuery && (
          <div className="flex flex-col items-center justify-center py-32 text-center">
            <div className="w-16 h-16 rounded bg-neutral-soft border border-slate-soft flex items-center justify-center mb-6">
              <Briefcase size={24} className="text-slate-ink/40" />
            </div>
            <h2 className="text-xl font-serif text-slate-ink mb-2">Board is empty</h2>
            <p className="text-slate-ink/60 mb-6 max-w-sm font-sans text-sm leading-relaxed">
              Click <strong className="text-spruce-green font-medium">Refresh Board</strong> above to fetch the latest opportunities into the directory.
            </p>
          </div>
        )}

        {(isLoading || filteredJobs.length > 0) && (
          <div className="border border-slate-soft bg-background flex flex-col -mx-px">
            {isLoading ? (
              Array.from({ length: 8 }).map((_, i) => (
                <div key={i} className="p-6 border-b border-slate-soft last:border-b-0 flex flex-col md:flex-row md:items-center justify-between gap-4 animate-pulse">
                  <div className="flex-1 space-y-3">
                    <div className="h-5 bg-slate-soft rounded w-3/4 max-w-[300px]"></div>
                    <div className="h-4 bg-slate-soft/50 rounded w-1/2 max-w-[200px]"></div>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="h-3 bg-slate-soft/50 rounded w-20"></div>
                    <div className="h-8 bg-slate-soft rounded w-24"></div>
                  </div>
                </div>
              ))
            ) : (
              filteredJobs.map((job: Job) => (
                <div 
                  key={job.id} 
                  onClick={() => setSelectedJob(job)}
                  className="bg-background p-6 border-b border-slate-soft last:border-b-0 hover:bg-neutral-soft transition-colors duration-200 cursor-pointer group flex flex-col md:flex-row md:items-start lg:items-center justify-between gap-4"
                >
                  <div className="flex-1 min-w-0 pr-4">
                    <div className="flex justify-between md:justify-start items-start md:items-center gap-4">
                      <h3 className="font-serif text-lg font-medium text-slate-ink group-hover:text-spruce-green transition-colors truncate">{job.title}</h3>
                      <span className="font-mono text-xs text-amber-clay uppercase tracking-wider shrink-0 hidden md:inline-block">{job.source}</span>
                    </div>
                    <p className="font-sans text-sm text-slate-ink/70 mt-1.5 truncate">
                      {job.company} — {job.location || (job.is_remote ? "Remote" : "Unknown")}
                    </p>
                  </div>
                  <div className="flex items-center gap-6 mt-3 md:mt-0 shrink-0">
                    <span className="font-mono text-xs text-slate-ink/40">
                      {job.posted_at ? new Date(job.posted_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : "—"}
                    </span>
                    <button 
                      onClick={(e) => { e.stopPropagation(); window.open(job.apply_url, '_blank', 'noopener,noreferrer'); }}
                      className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-sans font-medium text-spruce-green bg-transparent border border-spruce-green/30 hover:border-spruce-green hover:bg-spruce-green/5 rounded transition-all"
                    >
                      Apply <ExternalLink size={12} />
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {!isLoading && searchQuery && filteredJobs.length === 0 && currentJobs.length > 0 && (
          <div className="text-center py-24 font-serif text-slate-ink/60">
            No entries found for &ldquo;{searchQuery}&rdquo;.
          </div>
        )}

        {currentData && currentData.pages > 1 && (
          <div className="flex justify-between items-center mt-8">
            <span className="font-mono text-xs text-slate-ink/50 uppercase tracking-widest">
              Page {page} of {currentData.pages}
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-4 py-2 bg-transparent border border-slate-soft rounded disabled:opacity-30 text-sm font-medium hover:border-slate-ink/30 transition-colors text-slate-ink"
              >
                Prev
              </button>
              <button
                onClick={() => setPage(p => Math.min(currentData.pages, p + 1))}
                disabled={page === currentData.pages}
                className="px-4 py-2 bg-transparent border border-slate-soft rounded disabled:opacity-30 text-sm font-medium hover:border-slate-ink/30 transition-colors text-slate-ink"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      <JobDetailsSidebar 
        job={selectedJob} 
        onClose={() => setSelectedJob(null)} 
      />
    </div>
  );
}
