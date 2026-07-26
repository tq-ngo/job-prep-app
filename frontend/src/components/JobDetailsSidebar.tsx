"use client";

import { X, ExternalLink, MapPin, Building2, Calendar, Globe, Tag } from "lucide-react";
import { Job } from "@/lib/api";

interface JobDetailsSidebarProps {
  job: Job | null;
  onClose: () => void;
}

export default function JobDetailsSidebar({ job, onClose }: JobDetailsSidebarProps) {
  if (!job) return null;

  return (
    <>
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-slate-ink/20 backdrop-blur-sm z-40 transition-opacity"
        onClick={onClose}
      />
      
      {/* Slide-over panel */}
      <div className="fixed inset-y-0 right-0 z-50 w-full max-w-xl bg-background shadow-2xl flex flex-col border-l border-slate-soft">
        
        {/* Header */}
        <div className="px-8 py-8 border-b border-slate-soft flex justify-between items-start bg-neutral-soft/50">
          <div className="pr-8">
            <h1 className="text-2xl font-serif font-medium text-slate-ink leading-tight mb-3">
              {job.title}
            </h1>
            <div className="flex items-center gap-2 text-slate-ink/70 font-sans text-sm">
              <Building2 size={16} className="text-slate-ink/50" />
              <span className="font-medium">{job.company}</span>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="p-2 rounded hover:bg-slate-soft/50 transition-colors text-slate-ink/50 hover:text-slate-ink"
          >
            <X size={20} />
          </button>
        </div>

        {/* Content (Scrollable) */}
        <div className="flex-1 overflow-y-auto px-8 py-10 space-y-10">
          
          {/* Apply CTA */}
          <a 
            href={job.apply_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-center gap-2 w-full py-3.5 bg-spruce-green hover:bg-spruce-green-hover text-warm-ivory font-sans font-medium rounded transition-colors"
          >
            Apply for position <ExternalLink size={16} />
          </a>

          {/* Metadata Grid */}
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-transparent border border-slate-soft rounded p-5">
              <div className="flex items-center gap-2 text-slate-ink/50 text-xs font-mono uppercase tracking-wider mb-2">
                <MapPin size={14} /> Location
              </div>
              <span className="text-sm font-sans text-slate-ink font-medium">
                {job.location || (job.is_remote ? "Remote" : "Unknown")}
                {job.is_remote && job.location && " (Remote)"}
              </span>
            </div>

            <div className="bg-transparent border border-slate-soft rounded p-5">
              <div className="flex items-center gap-2 text-slate-ink/50 text-xs font-mono uppercase tracking-wider mb-2">
                <Calendar size={14} /> Date Posted
              </div>
              <span className="text-sm font-sans text-slate-ink font-medium">
                {job.posted_at ? new Date(job.posted_at).toLocaleDateString(undefined, {
                  year: 'numeric', month: 'long', day: 'numeric'
                }) : "Unknown"}
              </span>
            </div>

            <div className="bg-transparent border border-slate-soft rounded p-5">
              <div className="flex items-center gap-2 text-slate-ink/50 text-xs font-mono uppercase tracking-wider mb-2">
                <Globe size={14} /> Source
              </div>
              <span className="text-sm font-sans text-slate-ink font-medium uppercase tracking-wide">
                {job.source}
              </span>
            </div>

            <div className="bg-transparent border border-slate-soft rounded p-5">
              <div className="flex items-center gap-2 text-slate-ink/50 text-xs font-mono uppercase tracking-wider mb-2">
                <Tag size={14} /> Status
              </div>
              <span className={`text-sm font-sans font-medium ${job.is_active !== false ? 'text-spruce-green' : 'text-amber-clay'}`}>
                {job.is_active !== false ? "Open" : "Closed"}
              </span>
            </div>
          </div>

          {/* Salary if available */}
          {(job.salary_min || job.salary_max) && (
            <div className="bg-transparent border border-slate-soft rounded p-5">
              <h3 className="text-xs font-mono uppercase tracking-wider text-slate-ink/50 mb-2">Compensation</h3>
              <span className="text-lg font-serif font-medium text-slate-ink">
                {job.salary_min && `$${job.salary_min.toLocaleString()}`}
                {job.salary_min && job.salary_max && " – "}
                {job.salary_max && `$${job.salary_max.toLocaleString()}`}
                {job.salary_currency && job.salary_currency !== "USD" && ` ${job.salary_currency}`}
              </span>
            </div>
          )}

          <div className="border-t border-slate-soft" />

          {/* Job Description */}
          <div>
            <h3 className="text-xs font-mono uppercase tracking-wider text-slate-ink/50 mb-5">
              Description
            </h3>
            <div className="prose prose-slate max-w-none text-slate-ink/80 font-sans whitespace-pre-wrap leading-relaxed text-sm">
              {job.description || "No detailed description available."}
            </div>
          </div>

          {/* Skills if available */}
          {job.skills && job.skills.length > 0 && (
            <div>
              <h3 className="text-xs font-mono uppercase tracking-wider text-slate-ink/50 mb-4">Core Skills</h3>
              <div className="flex flex-wrap gap-2">
                {job.skills.map((skill, i) => (
                  <span key={i} className="px-3 py-1 bg-neutral-soft border border-slate-soft text-slate-ink text-xs font-mono rounded">
                    {skill}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
