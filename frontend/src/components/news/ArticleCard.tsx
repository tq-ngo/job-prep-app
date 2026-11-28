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
      className={cardClasses({
        tone: "outlined",
        padding: "md",
        interactive: true,
        className: "block group",
      })}
    >
      <div className="flex items-center gap-2 mb-3 flex-wrap">
        <Badge variant="source">{article.source_domain}</Badge>
        {article.categories?.map((cat) => (
          <Badge key={cat} variant="skill">
            {cat}
          </Badge>
        ))}
        {article.published_at && (
          <span className="ml-auto font-mono text-label-small text-on-surface-variant tabular-nums flex items-center gap-1">
            <Clock size={12} strokeWidth={1.5} aria-hidden="true" />
            <time dateTime={article.published_at}>{formatDate(article.published_at)}</time>
          </span>
        )}
      </div>

      <h2 className="text-title-large font-semibold text-on-surface group-hover:text-primary transition-colors mb-2 flex items-start gap-2">
        <span>{article.title || article.url}</span>
        <ExternalLink
          size={16}
          strokeWidth={1.5}
          aria-hidden="true"
          className="opacity-0 group-hover:opacity-100 transition-opacity mt-1 shrink-0 text-primary"
        />
      </h2>

      <p className="font-sans text-body-medium text-on-surface-variant leading-relaxed line-clamp-3">
        {article.summary || "No summary available."}
      </p>
      {!article.enriched_at && (
        <p className="mt-2 inline-flex items-center gap-1.5 font-mono text-label-small text-on-surface-variant">
          <Spinner size={12} /> Summary pending
        </p>
      )}

      <div className="flex items-center gap-1.5 mt-4 flex-wrap">
        {article.tags?.map((tag) => (
          <Badge key={tag} variant="neutral">
            <Tag size={10} strokeWidth={1.5} aria-hidden="true" /> {tag}
          </Badge>
        ))}
        {article.scraped_at && (
          <span suppressHydrationWarning className="ml-auto font-mono text-label-small text-on-surface-variant tabular-nums">
            Analyzed {timeAgo(article.scraped_at)}
          </span>
        )}
      </div>
    </a>
  );
}
