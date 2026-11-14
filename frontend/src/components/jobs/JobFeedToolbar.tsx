"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowUpDown, Check, RefreshCw, Search, Sparkles, X } from "lucide-react";
import {
  CATEGORIES,
  SORT_OPTIONS,
  SOURCES,
  SPONSORSHIPS,
  WORK_TYPES,
  type FilterKey,
  type JobFilters,
} from "@/lib/job-filters";
import { jobsApi } from "@/lib/api";
import Badge from "@/components/ui/Badge";
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
  const [sent, setSent] = useState(value);

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
      pill
      type="search"
      leadingIcon={<Search size={14} />}
      value={text}
      onChange={(e) => setText(e.target.value)}
      placeholder="Search role or company…"
      aria-label="Search role or company"
      className="w-full sm:w-60"
    />
  );
}

/**
 * Skills input with live autocomplete suggestions.
 */
function SkillAutocompleteInput({
  value,
  onSelectSkill,
}: {
  value: string;
  onSelectSkill: (skill: string) => void;
}) {
  const [query, setQuery] = useState(value);
  const [prevValue, setPrevValue] = useState(value);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const containerRef = useRef<HTMLDivElement>(null);

  if (value !== prevValue) {
    setPrevValue(value);
    setQuery(value);
  }

  useEffect(() => {
    let active = true;
    const timer = setTimeout(async () => {
      try {
        const list = await jobsApi.getSkills(query.trim());
        if (active) {
          setSuggestions(list);
        }
      } catch {
        if (active) setSuggestions([]);
      }
    }, 150);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [query]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleSelect = (s: string) => {
    setQuery(s);
    setOpen(false);
    onSelectSkill(s);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!open && (e.key === "ArrowDown" || e.key === "ArrowUp")) {
      setOpen(true);
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((prev) => (prev + 1 < suggestions.length ? prev + 1 : 0));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((prev) => (prev > 0 ? prev - 1 : suggestions.length - 1));
    } else if (e.key === "Enter") {
      if (open && activeIndex >= 0 && suggestions[activeIndex]) {
        e.preventDefault();
        handleSelect(suggestions[activeIndex]);
      } else if (query.trim()) {
        e.preventDefault();
        handleSelect(query.trim());
      }
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  return (
    <div ref={containerRef} className="relative w-full sm:w-52">
      <div className="relative">
        <Input
          size="sm"
          pill
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder="Filter by skill…"
          aria-label="Filter by skill"
          leadingIcon={<Sparkles size={13} className="text-spruce-green" />}
          className={cn("pr-7 text-xs", value && "border-spruce-green/50 bg-spruce-green/5")}
        />
        {value && (
          <button
            type="button"
            onClick={() => {
              setQuery("");
              onSelectSkill("");
            }}
            aria-label="Clear skill filter"
            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-foreground-subtle hover:text-slate-ink"
          >
            <X size={13} />
          </button>
        )}
      </div>

      {open && suggestions.length > 0 && (
        <ul
          role="listbox"
          aria-label="Suggested skills"
          className="absolute z-50 left-0 top-full mt-1.5 w-60 max-h-56 overflow-y-auto rounded-card border border-slate-soft bg-neutral-soft p-1 shadow-pop"
        >
          {suggestions.map((skill, index) => {
            const isSelected = skill.toLowerCase() === value.toLowerCase();
            const isActive = index === activeIndex;
            return (
              <li
                key={skill}
                role="option"
                aria-selected={isSelected}
                onMouseEnter={() => setActiveIndex(index)}
                onClick={() => handleSelect(skill)}
                className={cn(
                  "flex items-center justify-between px-3 py-1.5 rounded-control text-xs font-medium cursor-pointer transition-colors",
                  isActive ? "bg-surface-container text-slate-ink" : "text-foreground-muted hover:bg-surface-container",
                  isSelected && "text-spruce-green font-semibold bg-spruce-green/10",
                )}
              >
                <span>{skill}</span>
                {isSelected && <Check size={12} className="text-spruce-green" />}
              </li>
            );
          })}
        </ul>
      )}
    </div>
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
  const onSkill = useCallback((skill: string) => onFilter("skill", skill), [onFilter]);

  const activeFilters = [
    filters.q && { key: "q" as FilterKey, label: `Search: "${filters.q}"` },
    filters.category && { key: "category" as FilterKey, label: `Category: ${filters.category}` },
    filters.sponsorship && {
      key: "sponsorship" as FilterKey,
      label: SPONSORSHIPS.find((s) => s.value === filters.sponsorship)?.label ?? filters.sponsorship,
    },
    filters.work_type && {
      key: "work_type" as FilterKey,
      label: WORK_TYPES.find((w) => w.value === filters.work_type)?.label ?? filters.work_type,
    },
    filters.skill && { key: "skill" as FilterKey, label: `Skill: ${filters.skill}` },
    filters.source && {
      key: "source" as FilterKey,
      label: SOURCES.find((s) => s.value === filters.source)?.label ?? filters.source,
    },
  ].filter(Boolean) as { key: FilterKey; label: string }[];

  const clearAll = () => {
    onFilter("q", "");
    onFilter("category", "");
    onFilter("sponsorship", "");
    onFilter("work_type", "");
    onFilter("skill", "");
    onFilter("source", "");
  };

  return (
    <div className={cn("sticky top-12 z-30 bg-background/95 backdrop-blur-md border-b border-slate-soft shadow-xs transition-colors", className)}>
      <div className="w-full px-4 sm:px-6 lg:px-8 py-2.5 space-y-2">
        {/* Primary Controls Row */}
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-base font-serif font-medium text-slate-ink tracking-tight mr-1">Job Board</h1>
          <span className="font-mono text-2xs text-foreground-subtle uppercase tracking-wider mr-1.5 whitespace-nowrap">
            {totalLabel}
          </span>
          <span
            className="inline-flex items-center gap-1.5 font-mono text-2xs uppercase tracking-wider px-2 py-0.5 rounded-full bg-neutral-soft border border-slate-soft text-foreground-subtle mr-auto select-none"
            title={liveConnected ? "Live updates connected" : "Live updates disconnected"}
          >
            <span aria-hidden="true" className={cn("w-1.5 h-1.5 rounded-full", liveConnected ? "bg-spruce-green animate-pulse" : "bg-slate-soft")} />
            <span className="hidden sm:inline">{liveConnected ? "Live" : "Offline"}</span>
          </span>

          <SearchBox value={filters.q} onSearch={onSearch} />

          {/* Sort By */}
          <div className="flex items-center gap-1">
            <Select
              size="sm"
              aria-label="Sort by"
              value={filters.sort_by || "date"}
              onChange={(e) => onFilter("sort_by", e.target.value)}
              className="rounded-full bg-neutral-soft border-slate-soft hover:bg-surface-container text-xs pl-7"
            >
              {SORT_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </Select>
            <ArrowUpDown size={12} className="absolute ml-2.5 text-foreground-subtle pointer-events-none" />
          </div>

          <Button
            size="sm"
            className="rounded-full shadow-xs"
            onClick={onRefresh}
            loading={refreshing}
            icon={<RefreshCw size={12} aria-hidden="true" />}
          >
            {refreshing ? "Syncing…" : "Refresh"}
          </Button>
        </div>

        {/* Refined Filter Chips Row */}
        <div className="flex flex-wrap items-center gap-2 pt-0.5">
          {/* Sponsorship Filter */}
          <Select
            size="sm"
            aria-label="Visa Sponsorship"
            value={filters.sponsorship}
            onChange={(e) => onFilter("sponsorship", e.target.value)}
            className={cn(
              "rounded-full bg-neutral-soft border-slate-soft hover:bg-surface-container text-xs font-mono",
              filters.sponsorship && "border-spruce-green/50 bg-spruce-green/10 text-spruce-green font-medium",
            )}
          >
            <option value="">All Sponsorship</option>
            {SPONSORSHIPS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </Select>

          {/* Category Filter */}
          <Select
            size="sm"
            aria-label="Category"
            value={filters.category}
            onChange={(e) => onFilter("category", e.target.value)}
            className={cn(
              "rounded-full bg-neutral-soft border-slate-soft hover:bg-surface-container text-xs font-mono",
              filters.category && "border-spruce-green/50 bg-spruce-green/10 text-spruce-green font-medium",
            )}
          >
            <option value="">All Categories</option>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </Select>

          {/* Work Type Filter */}
          <Select
            size="sm"
            aria-label="Work Type"
            value={filters.work_type}
            onChange={(e) => onFilter("work_type", e.target.value)}
            className={cn(
              "rounded-full bg-neutral-soft border-slate-soft hover:bg-surface-container text-xs font-mono",
              filters.work_type && "border-spruce-green/50 bg-spruce-green/10 text-spruce-green font-medium",
            )}
          >
            <option value="">All Work Types</option>
            {WORK_TYPES.map((w) => (
              <option key={w.value} value={w.value}>
                {w.label}
              </option>
            ))}
          </Select>

          {/* Skills Filter with Autocomplete */}
          <SkillAutocompleteInput value={filters.skill} onSelectSkill={onSkill} />

          {/* Source Filter */}
          <Select
            size="sm"
            aria-label="Source"
            value={filters.source}
            onChange={(e) => onFilter("source", e.target.value)}
            className={cn(
              "rounded-full bg-neutral-soft border-slate-soft hover:bg-surface-container text-xs font-mono",
              filters.source && "border-spruce-green/50 bg-spruce-green/10 text-spruce-green font-medium",
            )}
          >
            <option value="">All Sources</option>
            {SOURCES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </Select>
        </div>

        {/* Active Filters Badges & Clear Affordance */}
        {activeFilters.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 pt-1">
            <span className="font-mono text-2xs uppercase tracking-wider text-foreground-subtle mr-1">
              Active Filters:
            </span>
            {activeFilters.map((af) => (
              <Badge key={af.key} variant="neutral" className="pl-2.5 pr-1 py-0.5 text-2xs gap-1 bg-surface-container border-slate-soft">
                <span>{af.label}</span>
                <button
                  type="button"
                  onClick={() => onFilter(af.key, "")}
                  aria-label={`Remove filter ${af.label}`}
                  className="rounded-full hover:bg-slate-ink/10 p-0.5 text-foreground-muted hover:text-slate-ink"
                >
                  <X size={10} />
                </button>
              </Badge>
            ))}
            <button
              type="button"
              onClick={clearAll}
              className="text-2xs font-mono text-spruce-green hover:underline ml-1.5"
            >
              Clear all
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
