"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";
import { ArrowUpDown, Check, Search, SlidersHorizontal, X } from "lucide-react";
import {
  CATEGORIES,
  SORT_OPTIONS,
  SPONSORSHIPS,
  WORK_TYPES,
  type FilterKey,
  type JobFilters,
} from "@/lib/job-filters";
import { jobsApi } from "@/lib/api";
import Badge from "@/components/ui/Badge";
import { cn } from "@/components/ui/cn";
import { Input } from "@/components/ui/Input";
import FilterDropdown from "@/components/ui/FilterDropdown";

const SEARCH_DEBOUNCE_MS = 250;

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
      type="search"
      leadingIcon={<Search size={14} strokeWidth={1.5} />}
      value={text}
      onChange={(e) => setText(e.target.value)}
      placeholder="Search role or company…"
      aria-label="Search role or company"
      className="w-full sm:w-60"
    />
  );
}

/**
 * Skills input with live autocomplete suggestions and WAI-ARIA Combobox semantics.
 * Fetches suggestions lazily only when opened.
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
  const listboxId = useId();

  if (value !== prevValue) {
    setPrevValue(value);
    setQuery(value);
  }

  useEffect(() => {
    if (!open) return;
    let active = true;
    const timer = setTimeout(async () => {
      try {
        const list = await jobsApi.getSkills(query.trim());
        if (active) {
          setSuggestions(list);
          setActiveIndex(-1);
        }
      } catch {
        if (active) setSuggestions([]);
      }
    }, 150);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [open, query]);

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
    setActiveIndex(-1);
    onSelectSkill(s);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!open && (e.key === "ArrowDown" || e.key === "ArrowUp")) {
      setOpen(true);
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (suggestions.length > 0) {
        setActiveIndex((prev) => (prev + 1 < suggestions.length ? prev + 1 : 0));
      }
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (suggestions.length > 0) {
        setActiveIndex((prev) => (prev > 0 ? prev - 1 : suggestions.length - 1));
      }
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
      setActiveIndex(-1);
    }
  };

  const listOpen = open && suggestions.length > 0;
  const activeOptionId = listOpen && activeIndex >= 0 ? `${listboxId}-opt-${activeIndex}` : undefined;

  return (
    <div ref={containerRef} className="relative w-full sm:w-52">
      <div className="relative">
        <Input
          size="sm"
          role="combobox"
          aria-expanded={listOpen}
          aria-controls={listOpen ? listboxId : undefined}
          aria-activedescendant={activeOptionId}
          aria-autocomplete="list"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder="Filter by skill…"
          aria-label="Filter by skill"
          leadingIcon={<SlidersHorizontal size={14} strokeWidth={1.5} />}
          inputClassName={cn(
            value && "pr-8 border-primary bg-primary-container text-on-primary-container placeholder:text-on-primary-container",
          )}
        />
        {value && (
          <button
            type="button"
            onClick={() => {
              setQuery("");
              onSelectSkill("");
            }}
            aria-label="Clear skill"
            className="absolute right-1 top-1/2 -translate-y-1/2 w-6 h-6 inline-flex items-center justify-center rounded-sm text-on-primary-container hover:bg-on-primary-container/12 transition-colors cursor-pointer"
          >
            <X size={12} strokeWidth={1.5} aria-hidden="true" />
          </button>
        )}
      </div>

      {listOpen && (
        <ul
          id={listboxId}
          role="listbox"
          aria-label="Suggested skills"
          className="absolute z-50 left-0 top-full mt-1.5 w-60 max-h-56 overflow-y-auto rounded-md border border-outline-variant bg-surface-container-lowest dark:bg-surface-container-default p-1.5 shadow-level-3 dark:shadow-none"
        >
          {suggestions.map((skill, index) => {
            const isSelected = skill.toLowerCase() === value.toLowerCase();
            const isActive = index === activeIndex;
            return (
              <li
                key={skill}
                id={`${listboxId}-opt-${index}`}
                role="option"
                aria-selected={isSelected}
                onMouseEnter={() => setActiveIndex(index)}
                onClick={() => handleSelect(skill)}
                className={cn(
                  "flex items-center justify-between gap-3 px-3 py-2 rounded-sm text-label-medium cursor-pointer transition-colors",
                  isSelected
                    ? "text-on-primary-container font-semibold bg-primary-container"
                    : isActive
                      ? "bg-on-surface/8 text-on-surface font-medium"
                      : "text-on-surface-variant hover:text-on-surface hover:bg-on-surface/8 font-medium",
                )}
              >
                <span>{skill}</span>
                {isSelected && <Check size={14} strokeWidth={1.5} aria-hidden="true" className="text-on-primary-container shrink-0" />}
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
  onClearAll: () => void;
  totalLabel: string;
  liveConnected: boolean;
  className?: string;
}

export default function JobFeedToolbar({
  filters,
  onFilter,
  onClearAll,
  totalLabel,
  liveConnected,
  className,
}: JobFeedToolbarProps) {
  const onSearch = useCallback((q: string) => onFilter("q", q), [onFilter]);
  const onSkill = useCallback((skill: string) => onFilter("skill", skill), [onFilter]);

  const activeFilters = [
    filters.sponsorship && {
      key: "sponsorship" as FilterKey,
      label: SPONSORSHIPS.find((s) => s.value === filters.sponsorship)?.label ?? filters.sponsorship,
    },
    filters.category && { key: "category" as FilterKey, label: filters.category },
    filters.work_type && {
      key: "work_type" as FilterKey,
      label: WORK_TYPES.find((w) => w.value === filters.work_type)?.label ?? filters.work_type,
    },
    filters.skill && { key: "skill" as FilterKey, label: `Skill: ${filters.skill}` },
  ].filter(Boolean) as { key: FilterKey; label: string }[];

  return (
    <div className={cn("sticky top-14 z-30 bg-surface/95 backdrop-blur-md border-b border-outline-variant transition-colors", className)}>
      <div className="w-full px-4 sm:px-6 lg:px-8 py-3 space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-title-medium font-semibold text-on-surface tracking-tight mr-1">Job Board</h1>
          <span className="font-mono text-label-small text-on-surface-variant tabular-nums mr-1.5 whitespace-nowrap">
            {totalLabel}
          </span>
          <span
            className="inline-flex items-center gap-1.5 font-mono text-label-small px-2.5 py-0.5 rounded-full bg-surface-container-low border border-outline-variant text-on-surface-variant mr-auto select-none"
            title={liveConnected ? "Live updates connected" : "Live updates disconnected"}
          >
            <span aria-hidden="true" className={cn("w-1.5 h-1.5 rounded-full", liveConnected ? "bg-primary" : "bg-outline-variant")} />
            <span className="hidden sm:inline">{liveConnected ? "Live" : "Offline"}</span>
          </span>

          <SearchBox value={filters.q} onSearch={onSearch} />

          <FilterDropdown
            value={filters.sort_by || "date"}
            defaultValue="date"
            onChange={(val) => onFilter("sort_by", val)}
            options={SORT_OPTIONS}
            placeholder="Sort by"
            leadingIcon={<ArrowUpDown size={14} strokeWidth={1.5} className="text-on-surface-variant" />}
            ariaLabel="Sort by"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2 pt-0.5">
          <FilterDropdown
            value={filters.sponsorship}
            onChange={(val) => onFilter("sponsorship", val)}
            options={SPONSORSHIPS}
            placeholder="All Sponsorship"
            allOptionLabel="All Sponsorship"
            ariaLabel="Visa Sponsorship"
          />

          <FilterDropdown
            value={filters.category}
            onChange={(val) => onFilter("category", val)}
            options={CATEGORIES.map((c) => ({ value: c, label: c }))}
            placeholder="All Categories"
            allOptionLabel="All Categories"
            ariaLabel="Category"
          />

          <FilterDropdown
            value={filters.work_type}
            onChange={(val) => onFilter("work_type", val)}
            options={WORK_TYPES}
            placeholder="All Work Types"
            allOptionLabel="All Work Types"
            ariaLabel="Work Type"
          />

          <SkillAutocompleteInput value={filters.skill} onSelectSkill={onSkill} />
        </div>

        {activeFilters.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 pt-1">
            <span className="text-label-small text-on-surface-variant">Active filters:</span>
            {activeFilters.map((af) => (
              <Badge key={af.key} variant="filter" className="pl-2 pr-0.5 py-0 gap-0.5">
                <span>{af.label}</span>
                <button
                  type="button"
                  onClick={() => onFilter(af.key, "")}
                  aria-label={`Remove filter ${af.label}`}
                  className="w-6 h-6 inline-flex items-center justify-center rounded-xs hover:bg-on-primary-container/12 text-on-primary-container transition-colors cursor-pointer"
                >
                  <X size={12} strokeWidth={1.5} aria-hidden="true" />
                </button>
              </Badge>
            ))}
            <button
              type="button"
              onClick={onClearAll}
              className="text-label-small font-medium text-primary hover:underline ml-1 cursor-pointer"
            >
              Clear all
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
