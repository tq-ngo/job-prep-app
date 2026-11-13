import { Button } from "@/components/ui/Button";

export default function JobListPagination({
  page,
  pages,
  total,
  capped,
  onPage,
}: {
  page: number;
  pages: number;
  total: number;
  capped?: boolean;
  onPage: (page: number) => void;
}) {
  if (pages <= 1) return null;
  return (
    <nav aria-label="Pagination" className="flex items-center justify-between gap-2 px-4 py-3 border-t border-slate-soft">
      <span className="font-mono text-2xs text-foreground-subtle uppercase tracking-wider">
        Page {page} of {pages} ({total}
        {capped ? "+" : ""} total)
      </span>
      <div className="flex gap-2">
        <Button variant="secondary" size="sm" className="rounded-full" onClick={() => onPage(page - 1)} disabled={page <= 1}>
          Prev
        </Button>
        <Button variant="secondary" size="sm" className="rounded-full" onClick={() => onPage(page + 1)} disabled={page >= pages}>
          Next
        </Button>
      </div>
    </nav>
  );
}
