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
          "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-label-medium font-medium border transition-all duration-150 cursor-pointer -outline-offset-2",
          isFiltered
            ? open
              ? "border-primary ring-2 ring-primary/25 bg-primary-container text-on-primary-container font-semibold shadow-level-1"
              : "border-primary/40 bg-primary-container text-on-primary-container font-semibold hover:shadow-level-1"
            : open
              ? "border-primary ring-2 ring-primary/20 bg-surface-container-default text-on-surface"
              : "border-outline-variant bg-surface-container-low text-on-surface hover:bg-on-surface/8 focus-visible:bg-on-surface/12 hover:border-outline",
        )}
      >
        {leadingIcon && <span className="shrink-0">{leadingIcon}</span>}
        <span className="truncate max-w-44">{displayLabel}</span>
        <ChevronDown
          size={12}
          className={cn(
            "shrink-0 transition-transform duration-150",
            isFiltered ? "text-on-primary-container" : "text-on-surface-variant",
            open && "rotate-180",
          )}
        />
      </button>

      {open && (
        <ul
          role="listbox"
          aria-label={ariaLabel || placeholder}
          className="absolute z-50 left-0 top-full mt-1.5 min-w-[190px] w-max max-h-64 overflow-y-auto rounded-md border border-outline-variant bg-surface-container-lowest dark:bg-surface-container-default p-1.5 shadow-level-3 animate-fadeSlideIn"
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
                "flex items-center justify-between gap-3 px-3 py-2 rounded-sm text-label-medium cursor-pointer transition-colors",
                !value
                  ? "text-on-primary-container font-semibold bg-primary-container"
                  : "text-on-surface-variant hover:text-on-surface hover:bg-on-surface/8 font-medium",
              )}
            >
              <span>{allOptionLabel}</span>
              {!value && <Check size={13} className="text-on-primary-container shrink-0" />}
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
                  "flex items-center justify-between gap-3 px-3 py-2 rounded-sm text-label-medium cursor-pointer transition-colors",
                  isSelected
                    ? "text-on-primary-container font-semibold bg-primary-container"
                    : "text-on-surface-variant hover:text-on-surface hover:bg-on-surface/8 font-medium",
                )}
              >
                <span>{opt.label}</span>
                {isSelected && <Check size={13} className="text-on-primary-container shrink-0" />}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

