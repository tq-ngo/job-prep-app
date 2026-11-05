import type { ReactNode } from "react";

/** Text for screen readers only, e.g. a label for an icon-only control. */
export default function VisuallyHidden({ children }: { children: ReactNode }) {
  return <span className="sr-only">{children}</span>;
}
