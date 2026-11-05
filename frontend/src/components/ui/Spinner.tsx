import { Loader2 } from "lucide-react";
import { cn } from "./cn";

/** Decorative spinner; pair it with visible or screen-reader text. */
export default function Spinner({ size = 14, className }: { size?: number; className?: string }) {
  return <Loader2 size={size} aria-hidden="true" className={cn("animate-spin shrink-0", className)} />;
}
