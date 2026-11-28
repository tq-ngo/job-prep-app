"use client";

import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
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
  /** Value considered neutral/unfiltered (e.g. "date" for sort order). */
  defaultValue?: string;
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
  defaultValue = "",
  leadingIcon,
  ariaLabel,
  className,
}: FilterDropdownProps) {
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const listboxRef = useRef<HTMLUListElement>(null);
  const listboxId = useId();

  const items = useMemo<FilterOption[]>(
    () => (allOptionLabel ? [{ value: "", label: allOptionLabel }, ...options] : [...options]),
    [allOptionLabel, options],
  );

  const selectedIndex = Math.max(
    0,
    items.findIndex((o) => o.value === value),
  );

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

  const closeAndReturnFocus = () => {
    setOpen(false);
    triggerRef.current?.focus();
  };

  const selectIndex = (index: number) => {
    const item = items[index];
    if (!item) return;
    onChange(item.value);
    closeAndReturnFocus();
  };

  const openMenu = (startIndex = selectedIndex) => {
    setActiveIndex(startIndex);
    setOpen(true);
  };

  useEffect(() => {
    if (open) {
      listboxRef.current?.focus({ preventScroll: true });
    }
  }, [open]);

  const handleTriggerKeyDown = (e: KeyboardEvent<HTMLButtonElement>) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp" || e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      if (open) {
        selectIndex(activeIndex);
      } else {
        openMenu(e.key === "ArrowUp" ? items.length - 1 : selectedIndex);
      }
    } else if (e.key === "Escape" && open) {
      e.preventDefault();
      closeAndReturnFocus();
    }
  };

  const handleListKeyDown = (e: KeyboardEvent<HTMLUListElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((prev) => (prev + 1) % items.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((prev) => (prev - 1 + items.length) % items.length);
    } else if (e.key === "Home") {
      e.preventDefault();
      setActiveIndex(0);
    } else if (e.key === "End") {
      e.preventDefault();
      setActiveIndex(items.length - 1);
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      selectIndex(activeIndex);
    } else if (e.key === "Escape") {
      e.preventDefault();
      closeAndReturnFocus();
    } else if (e.key === "Tab") {
      setOpen(false);
    }
  };

  const selectedOption = options.find((o) => o.value === value);
  const displayLabel = selectedOption ? selectedOption.label : allOptionLabel || placeholder;
  const isFiltered = Boolean(value) && value !== defaultValue;

  return (
    <div ref={containerRef} className={cn("relative inline-block select-none", className)}>
      <button
        ref={triggerRef}
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listboxId : undefined}
        aria-label={ariaLabel || placeholder}
        onClick={() => (open ? setOpen(false) : openMenu())}
        onKeyDown={handleTriggerKeyDown}
        className={cn(
          "inline-flex items-center gap-1.5 h-8 px-3 rounded-sm text-label-medium font-medium border transition-[background-color,border-color,color] duration-150 cursor-pointer -outline-offset-2",
          isFiltered
            ? open
              ? "border-primary bg-primary-container text-on-primary-container font-semibold"
              : "border-primary/40 bg-primary-container text-on-primary-container font-semibold"
            : open
              ? "border-primary bg-surface-container-default text-on-surface"
              : "border-outline-variant bg-surface-container-low text-on-surface hover:bg-on-surface/8 focus-visible:bg-on-surface/12 hover:border-outline",
        )}
      >
        {leadingIcon && <span className="shrink-0">{leadingIcon}</span>}
        <span className="truncate max-w-44">{displayLabel}</span>
        <ChevronDown
          size={14}
          strokeWidth={1.5}
          aria-hidden="true"
          className={cn(
            "shrink-0 transition-transform duration-150",
            isFiltered ? "text-on-primary-container" : "text-on-surface-variant",
            open && "rotate-180",
          )}
        />
      </button>

      {open && (
        <ul
          ref={listboxRef}
          id={listboxId}
          role="listbox"
          tabIndex={-1}
          aria-label={ariaLabel || placeholder}
          aria-activedescendant={`${listboxId}-opt-${activeIndex}`}
          onKeyDown={handleListKeyDown}
          className="absolute z-50 left-0 top-full mt-1.5 min-w-48 w-max max-h-64 overflow-y-auto rounded-md border border-outline-variant bg-surface-container-lowest dark:bg-surface-container-default p-1.5 shadow-level-3 dark:shadow-none animate-fadeSlideIn focus:outline-none"
        >
          {items.map((opt, index) => {
            const isSelected = opt.value === value;
            const isActive = index === activeIndex;
            return (
              <li
                key={opt.value || "__all__"}
                id={`${listboxId}-opt-${index}`}
                role="option"
                aria-selected={isSelected}
                onMouseEnter={() => setActiveIndex(index)}
                onClick={() => selectIndex(index)}
                className={cn(
                  "flex items-center justify-between gap-3 px-3 py-2 rounded-sm text-label-medium cursor-pointer transition-colors",
                  isSelected
                    ? "text-on-primary-container font-semibold bg-primary-container"
                    : isActive
                      ? "bg-on-surface/8 text-on-surface font-medium"
                      : "text-on-surface-variant hover:text-on-surface hover:bg-on-surface/8 font-medium",
                )}
              >
                <span>{opt.label}</span>
                {isSelected && <Check size={14} strokeWidth={1.5} aria-hidden="true" className="text-on-primary-container shrink-0" />}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
