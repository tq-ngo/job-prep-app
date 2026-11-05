import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

// Styles for every element markdownify emits from a sanitized JD. Tables
// render only because of remark-gfm: without it, GFM pipe tables showed up
// as literal "| a | b |" text. Headings are shifted down a level to sit
// under the pane's h2 title.
const markdownComponents: Components = {
  h1: (props) => <h3 className="text-lg font-serif font-semibold mt-5 mb-2 text-slate-ink" {...props} />,
  h2: (props) => <h3 className="text-base font-serif font-semibold mt-4 mb-2 text-slate-ink" {...props} />,
  h3: (props) => <h4 className="text-sm font-serif font-semibold mt-4 mb-1.5 text-slate-ink" {...props} />,
  h4: (props) => <h5 className="text-sm font-sans font-semibold mt-3 mb-1 text-slate-ink" {...props} />,
  h5: (props) => <h6 className="text-sm font-sans font-medium mt-3 mb-1 text-slate-ink" {...props} />,
  h6: (props) => <h6 className="text-xs font-sans font-semibold uppercase tracking-wider mt-3 mb-1 text-foreground-muted" {...props} />,
  p: (props) => <p className="mb-3 leading-relaxed" {...props} />,
  // list-outside + padding keeps wrapped bullet text aligned under the text,
  // not under the marker (list-inside broke that).
  ul: (props) => <ul className="list-disc list-outside pl-5 space-y-1 mb-3" {...props} />,
  ol: (props) => <ol className="list-decimal list-outside pl-5 space-y-1 mb-3" {...props} />,
  li: (props) => <li className="pl-0.5" {...props} />,
  strong: (props) => <strong className="font-semibold text-slate-ink" {...props} />,
  blockquote: (props) => (
    <blockquote className="border-l-2 border-spruce-green/40 pl-3 my-3 text-foreground-muted italic" {...props} />
  ),
  hr: () => <hr className="my-4 border-slate-soft" />,
  a: ({ href, ...props }) => (
    <a href={href} target="_blank" rel="noopener noreferrer nofollow" className="text-spruce-green underline underline-offset-2" {...props} />
  ),
  code: (props) => <code className="bg-neutral-soft px-1.5 py-0.5 rounded-control font-mono text-xs text-spruce-green" {...props} />,
  pre: (props) => <pre className="bg-neutral-soft p-3 rounded-control overflow-x-auto text-xs mb-3" {...props} />,
  table: (props) => (
    <div className="overflow-x-auto mb-3">
      <table className="w-full text-xs border-collapse border border-slate-soft" {...props} />
    </div>
  ),
  th: (props) => <th className="border border-slate-soft bg-neutral-soft px-2 py-1 text-left font-semibold" {...props} />,
  td: (props) => <td className="border border-slate-soft px-2 py-1 align-top" {...props} />,
};

/**
 * The job description, sanitized to Markdown at ingest. Raw HTML is never
 * rendered: rehype-raw is deliberately not used. Loaded with next/dynamic
 * so react-markdown stays off the board's critical path.
 */
export default function JobDescription({ markdown }: { markdown: string }) {
  return (
    <div className="text-slate-ink font-sans text-sm">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
        {markdown}
      </ReactMarkdown>
    </div>
  );
}
