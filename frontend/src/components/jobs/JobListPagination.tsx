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
    <nav aria-label="Pagination" className="flex items-center justify-between gap-2 px-4 py-3 border-t border-outline-variant">
      <span className="font-mono text-label-small text-on-surface-variant tabular-nums">
        Page {page} of {pages} ({total}
        {capped ? "+" : ""} total)
      </span>
      <div className="flex gap-2">
        <Button variant="outlined" size="sm" onClick={() => onPage(page - 1)} disabled={page <= 1}>
          Prev
        </Button>
        <Button variant="outlined" size="sm" onClick={() => onPage(page + 1)} disabled={page >= pages}>
          Next
        </Button>
      </div>
    </nav>
  );
}
