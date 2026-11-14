"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { Check, ChevronDown } from "lucide-react";
import { cn } from "./cn";

export interface FilterOption {
  value: string;
  label: string;
}

interface FilterDropdownProps {
  value: string;
  onChange: (value: string) => void;
  options: readonly FilterOption[] | FilterOption[];
  placeholder: string;
  allOptionLabel?: string;
  leadingIcon?: ReactNode;
  ariaLabel?: string;
  className?: string;
}

export default function FilterDropdown({
  value,
  onChange,
  options,
  placeholder,
  allOptionLabel,
  leadingIcon,
  ariaLabel,
  className,
}: FilterDropdownProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [open]);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    if (open) {
      document.addEventListener("keydown", handleKeyDown);
      return () => document.removeEventListener("keydown", handleKeyDown);
    }
  }, [open]);

  const selectedOption = options.find((o) => o.value === value);
  const displayLabel = selectedOption ? selectedOption.label : allOptionLabel || placeholder;
  const isFiltered = Boolean(value);

  return (
    <div ref={containerRef} className={cn("relative inline-block select-none", className)}>
      <button
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={ariaLabel || placeholder}
        onClick={() => setOpen((prev) => !prev)}
        className={cn(
          "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border transition-all duration-150 cursor-pointer shadow-xs -outline-offset-2",
          isFiltered
            ? open
              ? "border-tech-blue ring-2 ring-tech-blue/25 bg-tech-blue/15 text-tech-blue font-semibold"
              : "border-tech-blue/60 bg-tech-blue/10 text-tech-blue font-semibold"
            : open
              ? "border-tech-blue ring-2 ring-tech-blue/20 bg-surface-container text-slate-ink"
              : "border-slate-soft bg-neutral-soft text-foreground hover:bg-surface-container hover:border-slate-soft/80",
        )}
      >
        {leadingIcon && <span className="shrink-0">{leadingIcon}</span>}
        <span className="truncate max-w-44">{displayLabel}</span>
        <ChevronDown
          size={12}
          className={cn(
            "shrink-0 transition-transform duration-150",
            isFiltered ? "text-tech-blue" : "text-foreground-subtle",
            open && "rotate-180",
          )}
        />
      </button>

      {open && (
        <ul
          role="listbox"
          aria-label={ariaLabel || placeholder}
          className="absolute z-50 left-0 top-full mt-1.5 min-w-[190px] w-max max-h-64 overflow-y-auto rounded-card border border-slate-soft bg-surface-container-lowest dark:bg-surface-container p-1.5 shadow-pop animate-fadeSlideIn"
        >
          {allOptionLabel && (
            <li
              role="option"
              aria-selected={!value}
              onClick={() => {
                onChange("");
                setOpen(false);
              }}
              className={cn(
                "flex items-center justify-between gap-3 px-3 py-2 rounded-control text-xs cursor-pointer transition-colors",
                !value
                  ? "text-tech-blue font-semibold bg-tech-blue/10"
                  : "text-foreground-muted hover:text-slate-ink hover:bg-neutral-soft dark:hover:bg-surface-container-high font-medium",
              )}
            >
              <span>{allOptionLabel}</span>
              {!value && <Check size={13} className="text-tech-blue shrink-0" />}
            </li>
          )}

          {options.map((opt) => {
            const isSelected = opt.value === value;
            return (
              <li
                key={opt.value}
                role="option"
                aria-selected={isSelected}
                onClick={() => {
                  onChange(opt.value);
                  setOpen(false);
                }}
                className={cn(
                  "flex items-center justify-between gap-3 px-3 py-2 rounded-control text-xs cursor-pointer transition-colors",
                  isSelected
                    ? "text-tech-blue font-semibold bg-tech-blue/10"
                    : "text-foreground-muted hover:text-slate-ink hover:bg-neutral-soft dark:hover:bg-surface-container-high font-medium",
                )}
              >
                <span>{opt.label}</span>
                {isSelected && <Check size={13} className="text-tech-blue shrink-0" />}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
