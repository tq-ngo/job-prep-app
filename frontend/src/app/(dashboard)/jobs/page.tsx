"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getJobs, searchJobs, trackJob } from "@/api/jobs";
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { 
  ExternalLink, 
  Briefcase, 
  Search, 
  MapPin, 
  DollarSign, 
  Bookmark, 
  BookmarkCheck, 
  Globe, 
  Check, 
  SlidersHorizontal 
} from "lucide-react";
import SyncButton from "@/components/jobs/sync-button";
import { JobSearchItem } from "@/types";

export default function JobsPage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<"search" | "applications">("search");
  
  // Search parameters state
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [remoteOnly, setRemoteOnly] = useState(false);
  const [minSalary, setMinSalary] = useState<number | undefined>(undefined);
  const [skillsFilter, setSkillsFilter] = useState("");

  // Query for saved job applications (Tab 2)
  const { data: savedJobs, isLoading: isLoadingSaved } = useQuery({
    queryKey: ["jobs"],
    queryFn: getJobs,
    enabled: activeTab === "applications",
  });

  // Query for global jobs search (Tab 1)
  const { data: searchResults, isLoading: isLoadingSearch } = useQuery<JobSearchItem[]>({
    queryKey: ["jobs-search", debouncedQuery, skillsFilter, remoteOnly, minSalary],
    queryFn: () => searchJobs(debouncedQuery, skillsFilter || undefined, remoteOnly, minSalary),
    enabled: activeTab === "search",
  });

  // Mutation to track/save a global job
  const trackMutation = useMutation({
    mutationFn: ({ jobId, status }: { jobId: string; status: string }) => trackJob(jobId, status),
    onSuccess: () => {
      // Invalidate both caches to refresh lists
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["jobs-search"] });
    },
  });

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case "applied": return "bg-blue-500/10 text-blue-500 hover:bg-blue-500/20";
      case "interviewing": return "bg-orange-500/10 text-orange-500 hover:bg-orange-500/20";
      case "rejected": return "bg-red-500/10 text-red-500 hover:bg-red-500/20";
      case "offer": return "bg-green-500/10 text-green-500 hover:bg-green-500/20";
      default: return "bg-slate-500/10 text-slate-500 hover:bg-slate-500/20";
    }
  };

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(e.target.value);
    // Simple debounce trigger
    const timeoutId = setTimeout(() => {
      setDebouncedQuery(e.target.value);
    }, 200);
    return () => clearTimeout(timeoutId);
  };

  const isJobAlreadyTracked = (jobId: string) => {
    return savedJobs?.some(app => app.job_url === searchResults?.find(j => j.id === jobId)?.apply_url);
  };

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      {/* Header section */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-3xl font-extrabold tracking-tight bg-gradient-to-r from-slate-900 to-indigo-950 bg-clip-text text-transparent">
            Automated Job Portal
          </h2>
          <p className="text-muted-foreground">
            Explore global listings indexed in Elasticsearch and track your applications.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <SyncButton />
        </div>
      </div>

      {/* Tabs navigation */}
      <div className="flex border-b border-slate-200">
        <button
          onClick={() => setActiveTab("search")}
          className={`pb-3 px-6 text-sm font-semibold transition-all ${
            activeTab === "search"
              ? "border-b-2 border-indigo-600 text-indigo-600"
              : "text-muted-foreground hover:text-slate-900"
          }`}
        >
          Find Jobs
        </button>
        <button
          onClick={() => setActiveTab("applications")}
          className={`pb-3 px-6 text-sm font-semibold transition-all ${
            activeTab === "applications"
              ? "border-b-2 border-indigo-600 text-indigo-600"
              : "text-muted-foreground hover:text-slate-900"
          }`}
        >
          My Applications
        </button>
      </div>

      {/* Search & Global Directory Tab */}
      {activeTab === "search" && (
        <div className="space-y-6">
          {/* Filters Panel */}
          <div className="bg-white p-5 rounded-xl border border-slate-200/80 shadow-sm flex flex-col md:flex-row gap-4 items-center">
            <div className="relative flex-1 w-full">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <Input
                placeholder="Search job title, skills, keywords..."
                className="pl-9 h-11 w-full border-slate-200 focus-visible:ring-indigo-500"
                value={searchQuery}
                onChange={handleSearchChange}
              />
            </div>
            
            <div className="flex flex-wrap md:flex-nowrap gap-4 w-full md:w-auto items-center">
              {/* Remote only filter */}
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={remoteOnly}
                  onChange={(e) => setRemoteOnly(e.target.checked)}
                  className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 h-4 w-4"
                />
                <span className="text-sm font-medium text-slate-700 flex items-center gap-1">
                  <Globe className="h-4 w-4 text-slate-400" /> Remote Only
                </span>
              </label>

              {/* Salary filter */}
              <div className="relative w-full md:w-48">
                <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                <select
                  value={minSalary || ""}
                  onChange={(e) => setMinSalary(e.target.value ? Number(e.target.value) : undefined)}
                  className="pl-9 pr-4 h-11 w-full rounded-md border border-slate-200 bg-white text-sm font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="">Any Salary</option>
                  <option value="60000">$60k+ USD</option>
                  <option value="90000">$90k+ USD</option>
                  <option value="120000">$120k+ USD</option>
                  <option value="150000">$150k+ USD</option>
                  <option value="180000">$180k+ USD</option>
                </select>
              </div>
            </div>
          </div>

          {/* Results Grid */}
          {isLoadingSearch ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {[...Array(6)].map((_, i) => (
                <div key={i} className="animate-pulse bg-white border border-slate-200 rounded-xl h-52 p-5 space-y-4">
                  <div className="h-5 bg-slate-200 rounded w-2/3"></div>
                  <div className="h-4 bg-slate-200 rounded w-1/2"></div>
                  <div className="h-4 bg-slate-200 rounded w-full"></div>
                  <div className="h-8 bg-slate-200 rounded w-1/4 pt-2"></div>
                </div>
              ))}
            </div>
          ) : !searchResults || searchResults.length === 0 ? (
            <div className="text-center py-16 bg-white rounded-xl border border-slate-200/80">
              <div className="flex flex-col items-center gap-3">
                <Briefcase className="h-10 w-10 text-slate-300" />
                <h3 className="text-lg font-semibold text-slate-700">No jobs indexed yet</h3>
                <p className="text-muted-foreground max-w-sm">
                  We couldn't find any jobs matching your search parameters. Try crawling new listings.
                </p>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {searchResults.map((job) => {
                const tracked = savedJobs?.some(app => app.job_url === job.apply_url);
                return (
                  <div 
                    key={job.id} 
                    className="group relative bg-white border border-slate-200/80 hover:border-indigo-300 rounded-xl p-5 shadow-sm hover:shadow-md transition-all duration-300 hover:-translate-y-1 flex flex-col justify-between"
                  >
                    <div>
                      {/* Company Name & Score */}
                      <div className="flex items-center justify-between mb-3">
                        <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                          {job.company_name}
                        </span>
                        {job.quality_score > 0 && (
                          <Badge className="bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200/60 font-semibold">
                            Score: {job.quality_score}
                          </Badge>
                        )}
                      </div>

                      {/* Job Title */}
                      <h3 className="text-lg font-bold text-slate-900 group-hover:text-indigo-600 transition-colors mb-2 line-clamp-1">
                        {job.job_title}
                      </h3>

                      {/* Location & Remote Policy */}
                      <div className="flex items-center gap-4 text-xs font-medium text-slate-500 mb-4">
                        <span className="flex items-center gap-1">
                          <MapPin className="h-3.5 w-3.5 text-slate-400" /> {job.location || "Remote"}
                        </span>
                        <span className="flex items-center gap-1 capitalize">
                          <Globe className="h-3.5 w-3.5 text-slate-400" /> {job.remote_policy}
                        </span>
                      </div>

                      {/* Skills Badges */}
                      {job.skills_required && job.skills_required.length > 0 && (
                        <div className="flex flex-wrap gap-1.5 mb-5">
                          {job.skills_required.slice(0, 3).map((skill, index) => (
                            <Badge key={index} variant="secondary" className="bg-slate-100/80 text-slate-600 hover:bg-slate-100 text-[10px]">
                              {skill}
                            </Badge>
                          ))}
                          {job.skills_required.length > 3 && (
                            <span className="text-[10px] text-slate-400 font-bold self-center">
                              +{job.skills_required.length - 3} more
                            </span>
                          )}
                        </div>
                      )}
                    </div>

                    {/* Bottom CTA Block */}
                    <div className="border-t border-slate-100 pt-4 mt-auto flex items-center justify-between">
                      {job.salary_min_usd ? (
                        <span className="text-sm font-extrabold text-slate-800">
                          ${(job.salary_min_usd / 1000).toFixed(0)}k - ${(job.salary_max_usd ? job.salary_max_usd / 1000 : 0).toFixed(0)}k <span className="text-[10px] font-normal text-slate-400">/ yr</span>
                        </span>
                      ) : (
                        <span className="text-xs text-slate-400 italic font-medium">Salary undisclosed</span>
                      )}

                      <div className="flex items-center gap-2">
                        {/* Track / Save button */}
                        <Button
                          variant={tracked ? "secondary" : "outline"}
                          size="sm"
                          disabled={tracked || trackMutation.isPending}
                          onClick={() => trackMutation.mutate({ jobId: job.id, status: "Applied" })}
                          className={`h-8 px-3 rounded-lg ${tracked ? "text-emerald-600 bg-emerald-50 border-emerald-200" : ""}`}
                        >
                          {tracked ? (
                            <BookmarkCheck className="h-4 w-4" />
                          ) : (
                            <Bookmark className="h-4 w-4 text-slate-500" />
                          )}
                        </Button>

                        {/* Apply button */}
                        <Button 
                          variant="ghost"
                          size="sm"
                          className="h-8 w-8 p-0"
                          onClick={() => window.open(job.apply_url, "_blank")}
                        >
                          <ExternalLink className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Applications Tracking Tab (Existing page code, retrofitted with joins) */}
      {activeTab === "applications" && (
        <div className="rounded-xl border border-slate-200/80 bg-white shadow-sm overflow-hidden">
          <Table>
            <TableHeader className="bg-slate-50/50">
              <TableRow>
                <TableHead className="font-semibold text-slate-700">Company</TableHead>
                <TableHead className="font-semibold text-slate-700">Title</TableHead>
                <TableHead className="font-semibold text-slate-700">Source</TableHead>
                <TableHead className="font-semibold text-slate-700">Status</TableHead>
                <TableHead className="font-semibold text-slate-700">Date Applied</TableHead>
                <TableHead className="text-right font-semibold text-slate-700">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoadingSaved ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-12">
                    <span className="flex items-center justify-center gap-2 text-sm text-slate-500">
                      <Briefcase className="h-4 w-4 animate-bounce text-indigo-500" /> Loading saved applications...
                    </span>
                  </TableCell>
                </TableRow>
              ) : !savedJobs || savedJobs.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-12">
                    <div className="flex flex-col items-center gap-2">
                      <Briefcase className="h-8 w-8 text-muted-foreground" />
                      <p className="text-sm font-medium text-slate-500">No tracked applications yet. Head over to the Find Jobs tab to save one.</p>
                    </div>
                  </TableCell>
                </TableRow>
              ) : (
                savedJobs.map((job) => (
                  <TableRow key={job.id} className="hover:bg-slate-50/40 transition-colors">
                    <TableCell className="font-bold text-slate-900">{job.company_name}</TableCell>
                    <TableCell className="font-medium text-slate-700">{job.job_title}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className="bg-slate-50 text-slate-500 border-slate-200">
                        {job.source}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge className={getStatusColor(job.status)} variant="secondary">
                        {job.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-slate-500 text-sm font-medium">
                      {new Date(job.date_applied).toLocaleDateString()}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        className="h-8 w-8 p-0"
                        onClick={() => window.open(job.job_url, "_blank")}
                      >
                        <ExternalLink className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
