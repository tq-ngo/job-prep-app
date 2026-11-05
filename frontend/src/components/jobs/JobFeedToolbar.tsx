"use client";

import { useCallback, useEffect, useState } from "react";
import { RefreshCw, Search } from "lucide-react";
import { CATEGORIES, SOURCES, type FilterKey, type JobFilters } from "@/lib/job-filters";
import { Button } from "@/components/ui/Button";
import { cn } from "@/components/ui/cn";
import { Input, Select } from "@/components/ui/Input";

const SEARCH_DEBOUNCE_MS = 350;

/**
 * Search input that writes to the URL after a pause, and follows the URL
 * when it changes elsewhere (Back, "Clear filters").
 */
function SearchBox({ value, onSearch }: { value: string; onSearch: (q: string) => void }) {
  const [text, setText] = useState(value);
  const [urlValue, setUrlValue] = useState(value);
  // What this box last wrote; the URL catching up to it isn't an outside
  // change, and adopting it would drop anything typed since.
  const [sent, setSent] = useState(value);

  // Derive-from-props: adopt an outside URL change without an effect.
  if (value !== urlValue) {
    setUrlValue(value);
    if (value !== sent) setText(value);
  }

  useEffect(() => {
    const next = text.trim();
    if (next === value) return;
    const timer = setTimeout(() => {
      setSent(next);
      onSearch(next);
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [text, value, onSearch]);

  return (
    <Input
      size="sm"
      type="search"
      leadingIcon={<Search size={14} />}
      value={text}
      onChange={(e) => setText(e.target.value)}
      placeholder="Search role or company…"
      aria-label="Search role or company"
      className="w-full sm:w-64 order-last sm:order-none"
    />
  );
}

interface JobFeedToolbarProps {
  filters: JobFilters;
  onFilter: (key: FilterKey, value: string) => void;
  totalLabel: string;
  liveConnected: boolean;
  onRefresh: () => void;
  refreshing: boolean;
  className?: string;
}

export default function JobFeedToolbar({
  filters,
  onFilter,
  totalLabel,
  liveConnected,
  onRefresh,
  refreshing,
  className,
}: JobFeedToolbarProps) {
  const onSearch = useCallback((q: string) => onFilter("q", q), [onFilter]);
  return (
    <div className={cn("sticky top-12 z-30 bg-background/95 backdrop-blur-sm border-b border-slate-soft", className)}>
      <div className="max-w-app mx-auto px-4 sm:px-6 lg:px-8 py-2 flex flex-wrap items-center gap-2">
        <h1 className="text-base font-serif font-medium text-slate-ink tracking-tight mr-1">Job Board</h1>
        <span className="font-mono text-2xs text-foreground-subtle uppercase tracking-wider mr-2 whitespace-nowrap">{totalLabel}</span>
        <span
          className="inline-flex items-center gap-1.5 font-mono text-2xs uppercase tracking-wider text-foreground-subtle mr-auto"
          title={liveConnected ? "Live updates connected" : "Live updates disconnected"}
        >
          <span aria-hidden="true" className={cn("w-1.5 h-1.5 rounded-full", liveConnected ? "bg-spruce-green animate-pulse" : "bg-slate-soft")} />
          <span className="hidden sm:inline">{liveConnected ? "Live" : "Offline"}</span>
        </span>

        <SearchBox value={filters.q} onSearch={onSearch} />

        <Select size="sm" aria-label="Category" value={filters.category} onChange={(e) => onFilter("category", e.target.value)}>
          <option value="">All Categories</option>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </Select>

        <Select size="sm" aria-label="Source" value={filters.source} onChange={(e) => onFilter("source", e.target.value)}>
          <option value="">All Sources</option>
          {SOURCES.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </Select>

        <Button variant="secondary" size="sm" aria-pressed={filters.remote} onClick={() => onFilter("remote", filters.remote ? "" : "true")}>
          Remote
        </Button>

        <Button size="sm" onClick={onRefresh} loading={refreshing} icon={<RefreshCw size={12} aria-hidden="true" />}>
          {refreshing ? "Syncing…" : "Refresh"}
        </Button>
      </div>
    </div>
  );
}
