"use client";

import { createContext, useContext, useId, type ReactNode } from "react";
import { cn } from "./cn";

interface FieldControlProps {
  id: string;
  "aria-describedby"?: string;
  "aria-invalid"?: true;
}

const FieldContext = createContext<FieldControlProps | null>(null);

/**
 * The ids and ARIA wiring for the control inside a <Field>. Input, Select
 * and Textarea call this, so they're labelled and described automatically.
 */
export function useFieldControl(): FieldControlProps | null {
  return useContext(FieldContext);
}

interface FieldProps {
  label: ReactNode;
  /** Help text under the control, read out after the label. */
  hint?: ReactNode;
  /** Validation message. Marks the control invalid and is announced. */
  error?: ReactNode;
  /** False hides the label visually; screen readers still get it. */
  labelVisible?: boolean;
  className?: string;
  children: ReactNode;
}

/** Label + control + hint + error, wired together with ids. */
export default function Field({ label, hint, error, labelVisible = true, className, children }: FieldProps) {
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined;

  return (
    <div className={cn("space-y-1.5", className)}>
      <label htmlFor={id} className={labelVisible ? "block text-sm font-medium text-foreground" : "sr-only"}>
        {label}
      </label>
      <FieldContext.Provider value={{ id, "aria-describedby": describedBy, "aria-invalid": error ? true : undefined }}>
        {children}
      </FieldContext.Provider>
      {hint && (
        <p id={hintId} className="text-xs text-foreground-subtle">
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} className="text-xs font-medium text-amber-clay">
          {error}
        </p>
      )}
    </div>
  );
}
