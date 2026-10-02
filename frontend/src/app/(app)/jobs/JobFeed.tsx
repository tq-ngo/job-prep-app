"use client";

import { useState, useMemo, useCallback, useEffect } from "react";
import { useJobs, useTriggerScrape } from "@/hooks/useJobs";
import { useQueryClient } from "@tanstack/react-query";
import { Job, JobListResponse, jobsApi } from "@/lib/api";
import JobDetailsSidebar from "@/components/JobDetailsSidebar";
import { Search, ExternalLink, RefreshCw, Briefcase, Filter } from "lucide-react";
import { useScrapePolling } from "@/hooks/useScrapePolling";
import { useJobAlerts } from "@/hooks/useJobAlerts";
import { useSearchParams, useRouter, usePathname } from "next/navigation";

interface JobFeedProps {
  initialData?: JobListResponse;
}

export default function JobFeed({ initialData }: JobFeedProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const [page, setPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");

  // Server-side filters
  const [category, setCategory] = useState("");
  const [source, setSource] = useState("");
  const [isRemote, setIsRemote] = useState(false);

  // Scraping state for the pull mechanism
  const [taskId, setTaskId] = useState<string | null>(null);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);

  const queryClient = useQueryClient();

  // Debounce search input to query server across all database rows
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery.trim());
      setPage(1);
    }, 350);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const { connected: sseConnected } = useJobAlerts({
    onNewJob: useCallback(() => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    }, [queryClient]),
  });

  // Data fetching: combines server pagination + debounced search + filters
  const { data: jobsResponse, isLoading, refetch } = useJobs({ 
    page, 
    page_size: 30,
    category: category || undefined,
    is_remote: isRemote || undefined,
    source: source || undefined,
    q: debouncedSearch || undefined,
  });

  const triggerScrape = useTriggerScrape();

  const onScrapeComplete = useCallback(() => {
    setTaskId(null);
    refetch();
  }, [refetch]);

  useScrapePolling(taskId, onScrapeComplete);

  const handleRefreshScrapers = () => {
    refetch();
    const scrapeSource = source || "all";
    triggerScrape.mutate(scrapeSource, {
      onSuccess: (data) => {
        if (data.task_id) {
          setTaskId(data.task_id);
        } else {
          refetch();
        }
      }
    });
  };

  const isDefaultState = page === 1 && !isRemote && !source && !category && !debouncedSearch;
  const currentData = isDefaultState && !jobsResponse ? initialData : jobsResponse;
  
  const currentJobs = useMemo(() => {
    return currentData?.items ?? [];
  }, [currentData]);

  // URL Deep-linking (?jobId=<id>)
  const activeJobId = searchParams.get("jobId");

  useEffect(() => {
    if (activeJobId) {
      if (selectedJob?.id === activeJobId) return;
      const found = currentJobs.find((j) => j.id === activeJobId);
      if (found) {
        setSelectedJob(found);
      } else {
        jobsApi.get(activeJobId).then(setSelectedJob).catch(() => {});
      }
    } else if (!activeJobId && selectedJob) {
      setSelectedJob(null);
    }
  }, [activeJobId, currentJobs]);

  const handleSelectJob = (job: Job) => {
    setSelectedJob(job);
    const params = new URLSearchParams(searchParams.toString());
    params.set("jobId", job.id);
    router.push(`${pathname}?${params.toString()}`, { scroll: false });
  };

  const handleCloseDrawer = () => {
    setSelectedJob(null);
    const params = new URLSearchParams(searchParams.toString());
    params.delete("jobId");
    const newQuery = params.toString();
    router.push(newQuery ? `${pathname}?${newQuery}` : pathname, { scroll: false });
  };

  const isScraping = triggerScrape.isPending || !!taskId;

  return (
    <div className="min-h-screen bg-background text-foreground font-sans">

      {/* High-Density Header & Filter Bar */}
      <div className="bg-background border-b border-slate-soft pt-6 pb-4">
        <div className="max-w-[1500px] mx-auto px-4 sm:px-6 lg:px-8">
          
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 mb-4">
            <div>
              <h1 className="text-2xl font-serif font-medium text-slate-ink tracking-tight">Job Board</h1>
              <p className="font-mono text-xs text-foreground-muted mt-1 uppercase tracking-wider">
                {currentData ? `${currentData.total} positions tracked` : "Scanning live opportunities..."}
                {debouncedSearch && ` · matching "${debouncedSearch}"`}
              </p>
            </div>
            
            {/* Action Bar */}
            <div className="flex items-center gap-2">
              <button
                onClick={handleRefreshScrapers}
                disabled={isScraping}
                className="flex items-center gap-2 bg-spruce-green hover:bg-spruce-green-hover disabled:bg-slate-soft disabled:text-foreground-subtle text-warm-ivory px-4 py-2 rounded font-sans font-medium transition-colors text-xs border border-transparent shadow-sm"
              >
                <RefreshCw size={13} className={isScraping ? "animate-spin" : ""} />
                {isScraping ? "Syncing..." : "Refresh Board"}
              </button>
            </div>
          </div>

          <div className="flex flex-col sm:flex-row gap-3 sm:items-center">
            {/* Search Bar */}
            <div className="flex-1 max-w-md relative">
              <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-foreground-subtle" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search across all listings by role or company..."
                className="w-full pl-9 pr-8 py-2 bg-background border border-slate-soft rounded focus:outline-none focus:ring-1 focus:ring-spruce-green text-xs text-slate-ink placeholder:text-foreground-subtle transition-all font-sans"
              />
              {searchQuery && (
                <button 
                  onClick={() => setSearchQuery("")}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-xs text-foreground-subtle hover:text-slate-ink"
                >
                  ✕
                </button>
              )}
            </div>

            {/* Filter controls */}
            <div className="flex flex-wrap gap-2 items-center sm:ml-auto">
              <select
                value={category}
                onChange={(e) => { setCategory(e.target.value); setPage(1); }}
                className="appearance-none bg-background border border-slate-soft hover:border-slate-soft/80 text-slate-ink text-xs font-sans rounded px-3 py-2 focus:outline-none focus:ring-1 focus:ring-spruce-green transition-all cursor-pointer"
              >
                <option value="">All Categories</option>
                <option value="FAANG+">FAANG+</option>
                <option value="Quant">Quant</option>
                <option value="Others">Others</option>
              </select>

              <select
                value={source}
                onChange={(e) => { setSource(e.target.value); setPage(1); }}
                className="appearance-none bg-background border border-slate-soft hover:border-slate-soft/80 text-slate-ink text-xs font-sans rounded px-3 py-2 focus:outline-none focus:ring-1 focus:ring-spruce-green transition-all cursor-pointer"
              >
                <option value="">All Sources</option>
                <option value="github">GitHub</option>
                <option value="linkedin">LinkedIn</option>
              </select>

              <button
                type="button"
                onClick={() => { setIsRemote(!isRemote); setPage(1); }}
                className={`text-xs font-sans font-medium rounded px-3 py-2 border transition-all ${
                  isRemote 
                    ? "bg-amber-clay/10 border-amber-clay/40 text-amber-clay" 
                    : "bg-background border-slate-soft hover:border-slate-soft/80 text-slate-ink"
                }`}
              >
                Remote
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content Area: High-Density Table */}
      <div className="max-w-[1500px] mx-auto px-4 sm:px-6 lg:px-8 py-6">

        {/* Empty state */}
        {!isLoading && currentJobs.length === 0 && (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <div className="w-14 h-14 rounded-lg bg-neutral-soft border border-slate-soft flex items-center justify-center mb-4">
              <Briefcase size={22} className="text-foreground-subtle" />
            </div>
            <h2 className="text-lg font-serif text-slate-ink mb-1.5">No positions found</h2>
            <p className="text-foreground-muted mb-5 max-w-sm font-sans text-xs leading-relaxed">
              {debouncedSearch 
                ? `No job matches for "${debouncedSearch}". Try a different keyword or clear your filters.`
                : "The board is waiting for the daily crawler or manual refresh."}
            </p>
            {debouncedSearch && (
              <button
                onClick={() => setSearchQuery("")}
                className="px-3.5 py-1.5 bg-neutral-soft border border-slate-soft rounded text-xs text-slate-ink hover:border-spruce-green"
              >
                Clear Search
              </button>
            )}
          </div>
        )}

        {/* 6-Column Data Feed Table */}
        {(isLoading || currentJobs.length > 0) && (
          <div className="border border-slate-soft rounded-lg overflow-hidden bg-background shadow-xs">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-soft bg-neutral-soft/50">
                    <th className="px-4 py-3 font-mono text-[10px] font-semibold uppercase tracking-wider text-foreground-subtle">Role</th>
                    <th className="px-4 py-3 font-mono text-[10px] font-semibold uppercase tracking-wider text-foreground-subtle">Company</th>
                    <th className="px-4 py-3 font-mono text-[10px] font-semibold uppercase tracking-wider text-foreground-subtle">Location</th>
                    <th className="px-4 py-3 font-mono text-[10px] font-semibold uppercase tracking-wider text-foreground-subtle">Source</th>
                    <th className="px-4 py-3 font-mono text-[10px] font-semibold uppercase tracking-wider text-foreground-subtle text-right">Apply</th>
                    <th className="px-4 py-3 font-mono text-[10px] font-semibold uppercase tracking-wider text-foreground-subtle text-right">Posted</th>
                  </tr>
                </thead>
                <tbody>
                  {isLoading ? (
                    Array.from({ length: 10 }).map((_, i) => (
                      <tr key={i} className="border-b border-slate-soft/50">
                        <td colSpan={6} className="px-4 py-3.5">
                          <div className="animate-pulse flex gap-6">
                            <div className="h-3.5 w-48 bg-slate-soft rounded" />
                            <div className="h-3.5 w-24 bg-slate-soft/60 rounded" />
                            <div className="h-3.5 w-32 bg-slate-soft/60 rounded" />
                          </div>
                        </td>
                      </tr>
                    ))
                  ) : (
                    currentJobs.map((job: Job) => {
                      const isSelected = selectedJob?.id === job.id;
                      return (
                        <tr 
                          key={job.id} 
                          onClick={() => handleSelectJob(job)}
                          className={`border-b border-slate-soft/50 last:border-b-0 hover:bg-slate-soft/20 cursor-pointer transition-colors group ${
                            isSelected ? "bg-spruce-green/5 border-l-2 border-l-spruce-green" : ""
                          }`}
                          role="button"
                          tabIndex={0}
                          onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") handleSelectJob(job); }}
                        >
                          <td className="px-4 py-3 font-sans font-medium text-slate-ink group-hover:text-spruce-green transition-colors truncate max-w-[280px]">
                            {job.title}
                          </td>
                          <td className="px-4 py-3 font-sans text-foreground-muted truncate max-w-[160px]">
                            {job.company}
                          </td>
                          <td className="px-4 py-3 font-sans text-foreground-subtle truncate max-w-[160px]">
                            {job.location || (job.is_remote ? "Remote" : "—")}
                          </td>
                          <td className="px-4 py-3">
                            <span className="font-mono text-[10px] text-amber-clay uppercase tracking-wider px-1.5 py-0.5 rounded bg-amber-clay/10">
                              {job.source}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-right">
                            <a 
                              href={job.apply_url} 
                              target="_blank" 
                              rel="noopener noreferrer"
                              onClick={(e) => e.stopPropagation()}
                              className="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-sans font-medium text-spruce-green bg-spruce-green/5 border border-spruce-green/30 hover:border-spruce-green hover:bg-spruce-green/10 rounded transition-all"
                            >
                              Apply <ExternalLink size={11} />
                            </a>
                          </td>
                          <td className="px-4 py-3 text-right font-mono text-[10px] text-foreground-subtle whitespace-nowrap">
                            {job.posted_at 
                              ? new Date(job.posted_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
                              : "—"
                            }
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Pagination Bar */}
        {currentData && currentData.pages > 1 && (
          <div className="flex justify-between items-center mt-6">
            <span className="font-mono text-xs text-foreground-subtle uppercase tracking-wider">
              Page {page} of {currentData.pages} ({currentData.total} total)
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-3 py-1.5 bg-background border border-slate-soft rounded disabled:opacity-30 text-xs font-medium hover:border-slate-soft/80 transition-colors text-slate-ink cursor-pointer"
              >
                Prev
              </button>
              <button
                onClick={() => setPage((p) => Math.min(currentData.pages, p + 1))}
                disabled={page === currentData.pages}
                className="px-3 py-1.5 bg-background border border-slate-soft rounded disabled:opacity-30 text-xs font-medium hover:border-slate-soft/80 transition-colors text-slate-ink cursor-pointer"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Slide-over Sheet / Drawer */}
      <JobDetailsSidebar 
        job={selectedJob} 
        onClose={handleCloseDrawer} 
      />
    </div>
  );
}
