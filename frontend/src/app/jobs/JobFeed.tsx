"use client";

import { useState, useMemo, useCallback } from "react";
import { useJobs, useTriggerScrape } from "@/hooks/useJobs";
import { useQueryClient } from "@tanstack/react-query";
import { Job, JobListResponse } from "@/lib/api";
import JobDetailsSidebar from "@/components/JobDetailsSidebar";
import { Search, ExternalLink, RefreshCw, Briefcase } from "lucide-react";
import { useScrapePolling } from "@/hooks/useScrapePolling";
import { useJobAlerts } from "@/hooks/useJobAlerts";

interface JobFeedProps {
  initialData?: JobListResponse;
}

export default function JobFeed({ initialData }: JobFeedProps) {
  const [page, setPage] = useState(1);

  // Client-side search (spec: use filter() only, not server-side)
  const [searchQuery, setSearchQuery] = useState("");

  // Server-side filters (passed as API query params)
  const [category, setCategory] = useState("");
  const [source, setSource] = useState("");
  const [isRemote, setIsRemote] = useState(false);

  // Scraping state for the pull mechanism
  const [taskId, setTaskId] = useState<string | null>(null);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);

  const queryClient = useQueryClient();

  const { connected: sseConnected } = useJobAlerts({
    onNewJob: useCallback(() => {
      // Invalidate the jobs query cache — React Query will refetch in background
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    }, [queryClient]),
  });

  // Data fetching
  const { data: jobsResponse, isLoading, refetch } = useJobs({ 
    page, 
    page_size: 30,
    category: category || undefined,
    is_remote: isRemote || undefined,
    source: source || undefined
  });

  const triggerScrape = useTriggerScrape();

  // Stable callback for polling completion
  const onScrapeComplete = useCallback(() => {
    setTaskId(null);
    refetch();
  }, [refetch]);

  useScrapePolling(taskId, onScrapeComplete);

  // Trigger scraper matching current source filter, or all scrapers when unfiltered
  const handleRefreshScrapers = () => {
    const scrapeSource = source || "all";
    triggerScrape.mutate(scrapeSource, {
      onSuccess: (data) => {
        if (data.task_id) {
          setTaskId(data.task_id);
        } else {
          // Scrape already in progress — just refetch current data from DB
          refetch();
        }
      }
    });
  };

  // Determine which data to show (SSR initial vs client-fetched)
  const isDefaultState = page === 1 && !isRemote && !source && !category;
  const currentData = isDefaultState && !jobsResponse ? initialData : jobsResponse;
  
  const currentJobs = useMemo(() => {
    return currentData?.items ?? [];
  }, [currentData]);

  // CLIENT-SIDE search filter (spec: "Must use standard filter() operations")
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
        <div className="max-w-[1400px] mx-auto px-8 lg:px-12">
          <div className="flex justify-between items-end mb-8">
            <div>
              <h1 className="text-3xl font-serif font-medium text-slate-ink tracking-tight">Job Board</h1>
              <p className="font-mono text-xs text-slate-ink/60 mt-3 uppercase tracking-widest">
                {currentData ? `${currentData.total} positions tracked` : "Click Refresh to start scraping"}
              </p>
            </div>
            
            {/* "Refresh" Action Button */}
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
            {/* Client-side search bar */}
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

            {/* Filter pills */}
            <div className="flex flex-wrap gap-3 items-center lg:ml-auto">
              {/* Category Filter */}
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

              {/* Source Filter */}
              <select
                value={source}
                onChange={(e) => { setSource(e.target.value); setPage(1); }}
                className="appearance-none bg-transparent border border-slate-soft hover:border-slate-ink/20 text-slate-ink text-sm font-sans rounded px-4 py-2.5 focus:outline-none focus:ring-1 focus:ring-spruce-green transition-all cursor-pointer"
              >
                <option value="">All Sources</option>
                <option value="github">GitHub</option>
                <option value="linkedin">LinkedIn</option>
              </select>

              {/* Remote Toggle */}
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

      {/* Main Content Area: 6-Column Table */}
      <div className="max-w-[1400px] mx-auto px-8 lg:px-12 py-8">

        {/* Empty state CTA */}
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

        {/* Spec-compliant 6-column table */}
        {(isLoading || filteredJobs.length > 0) && (
          <div className="border border-slate-soft rounded overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-sm">
                <thead>
                  <tr className="border-b border-slate-soft">
                    <th className="px-5 py-3.5 font-mono text-[11px] font-semibold uppercase tracking-wider text-slate-ink/50">Role</th>
                    <th className="px-5 py-3.5 font-mono text-[11px] font-semibold uppercase tracking-wider text-slate-ink/50">Company</th>
                    <th className="px-5 py-3.5 font-mono text-[11px] font-semibold uppercase tracking-wider text-slate-ink/50">Location</th>
                    <th className="px-5 py-3.5 font-mono text-[11px] font-semibold uppercase tracking-wider text-slate-ink/50">Source</th>
                    <th className="px-5 py-3.5 font-mono text-[11px] font-semibold uppercase tracking-wider text-slate-ink/50 text-right">Apply</th>
                    <th className="px-5 py-3.5 font-mono text-[11px] font-semibold uppercase tracking-wider text-slate-ink/50 text-right">Date Posted</th>
                  </tr>
                </thead>
                <tbody>
                  {isLoading ? (
                    Array.from({ length: 8 }).map((_, i) => (
                      <tr key={i} className="border-b border-slate-soft/50">
                        <td colSpan={6} className="px-5 py-4">
                          <div className="animate-pulse flex gap-8">
                            <div className="h-4 w-48 bg-slate-soft rounded"></div>
                            <div className="h-4 w-24 bg-slate-soft/50 rounded"></div>
                            <div className="h-4 w-32 bg-slate-soft/50 rounded"></div>
                          </div>
                        </td>
                      </tr>
                    ))
                  ) : (
                    filteredJobs.map((job: Job) => (
                      <tr 
                        key={job.id} 
                        onClick={() => setSelectedJob(job)}
                        className="border-b border-slate-soft/50 last:border-b-0 hover:bg-slate-soft/20 cursor-pointer transition-colors group"
                        role="button"
                        tabIndex={0}
                        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") setSelectedJob(job); }}
                      >
                        <td className="px-5 py-3.5 font-sans font-medium text-slate-ink group-hover:text-spruce-green transition-colors truncate max-w-[280px]">
                          {job.title}
                        </td>
                        <td className="px-5 py-3.5 font-sans text-foreground truncate max-w-[180px]">
                          {job.company}
                        </td>
                        <td className="px-5 py-3.5 font-sans text-slate-ink/60 truncate max-w-[180px]">
                          {job.location || (job.is_remote ? "Remote" : "—")}
                        </td>
                        <td className="px-5 py-3.5">
                          <span className="font-mono text-xs text-amber-clay uppercase tracking-wider">
                            {job.source}
                          </span>
                        </td>
                        <td className="px-5 py-3.5 text-right">
                          <a 
                            href={job.apply_url} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-sans font-medium text-spruce-green bg-transparent border border-spruce-green/30 hover:border-spruce-green hover:bg-spruce-green/5 rounded transition-all"
                          >
                            Apply <ExternalLink size={12} />
                          </a>
                        </td>
                        <td className="px-5 py-3.5 text-right font-mono text-xs text-slate-ink/40 whitespace-nowrap">
                          {job.posted_at 
                            ? new Date(job.posted_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
                            : "—"
                          }
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* No search results */}
        {!isLoading && searchQuery && filteredJobs.length === 0 && currentJobs.length > 0 && (
          <div className="text-center py-24 font-serif text-slate-ink/60">
            No entries found for &ldquo;{searchQuery}&rdquo;.
          </div>
        )}

        {/* Pagination */}
        {currentData && currentData.pages > 1 && (
          <div className="flex justify-between items-center mt-8">
            <span className="font-mono text-xs text-slate-ink/50 uppercase tracking-widest">
              Page {page} of {currentData.pages} ({currentData.total} total)
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

      {/* Detail Overlay */}
      <JobDetailsSidebar 
        job={selectedJob} 
        onClose={() => setSelectedJob(null)} 
      />
    </div>
  );
}
