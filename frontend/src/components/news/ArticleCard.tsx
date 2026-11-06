import { Clock, ExternalLink, Tag } from "lucide-react";
import type { NewsArticle } from "@/lib/api";
import { formatDate } from "@/lib/format";
import Badge from "@/components/ui/Badge";
import { cardClasses } from "@/components/ui/Card";
import Spinner from "@/components/ui/Spinner";

function timeAgo(iso: string, now = Date.now()): string {
  const minutes = Math.floor((now - new Date(iso).getTime()) / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

/** One article on the radar; the whole card links to the source. */
export default function ArticleCard({ article }: { article: NewsArticle }) {
  return (
    <a
      href={article.url}
      target="_blank"
      rel="noopener noreferrer"
      className={cardClasses({ padding: "lg", className: "block hover:bg-neutral-soft transition-colors duration-200 group" })}
    >
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <span className="font-mono text-2xs font-medium uppercase tracking-wider text-amber-clay">{article.source_domain}</span>
        {article.categories?.map((cat) => (
          <span key={cat} className="font-mono text-2xs font-medium uppercase tracking-wider text-spruce-green">
            • {cat}
          </span>
        ))}
        {article.published_at && (
          <span className="ml-auto font-mono text-2xs text-foreground-subtle flex items-center gap-1">
            <Clock size={10} aria-hidden="true" />
            <time dateTime={article.published_at}>{formatDate(article.published_at)}</time>
          </span>
        )}
      </div>

      <h2 className="text-xl font-serif font-medium text-slate-ink group-hover:text-spruce-green transition-colors mb-3 flex items-start gap-2">
        {article.title || article.url}
        <ExternalLink size={14} aria-hidden="true" className="opacity-0 group-hover:opacity-100 transition-opacity mt-1 shrink-0 text-spruce-green" />
      </h2>

      <p className="font-sans text-sm text-foreground-muted leading-relaxed line-clamp-3">{article.summary || "No summary available."}</p>
      {!article.enriched_at && (
        <p className="mt-2 inline-flex items-center gap-1.5 font-mono text-2xs uppercase tracking-wider text-foreground-subtle">
          <Spinner size={11} /> AI summary pending
        </p>
      )}

      <div className="flex items-center gap-2 mt-4 flex-wrap">
        {article.tags?.map((tag) => (
          <Badge key={tag}>
            <Tag size={8} aria-hidden="true" /> {tag}
          </Badge>
        ))}
        {article.scraped_at && (
          // Relative to now, so the server render and hydration can differ.
          <span suppressHydrationWarning className="ml-auto font-mono text-2xs text-foreground-subtle">
            Analyzed {timeAgo(article.scraped_at)}
          </span>
        )}
      </div>
    </a>
  );
}
