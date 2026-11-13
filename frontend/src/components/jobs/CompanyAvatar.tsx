import { cn } from "@/components/ui/cn";

/**
 * Initials avatar. This used to request `logo.clearbit.com/<guess>.com`:
 * a third-party call that leaked viewers' IPs and the roles they browsed,
 * and whose domain guess was wrong for most multi-word names.
 */
export default function CompanyAvatar({ company, size = "md" }: { company: string; size?: "md" | "lg" }) {
  const initials = company
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase())
    .join("");
  return (
    <div
      aria-hidden="true"
      className={cn(
        "rounded-xl border border-slate-soft/80 bg-gradient-to-br from-spruce-green/15 to-amber-clay/10 shadow-xs",
        "flex items-center justify-center shrink-0 font-serif font-semibold text-spruce-green select-none",
        size === "lg" ? "w-12 h-12 text-base" : "w-10 h-10 text-sm",
      )}
    >
      {initials || "?"}
    </div>
  );
}
