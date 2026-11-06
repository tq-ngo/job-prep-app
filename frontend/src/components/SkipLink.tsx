/**
 * First focusable element on the page: lets keyboard and screen-reader
 * users jump past the navigation to `#main`. Hidden until focused.
 */
export default function SkipLink() {
  return (
    <a
      href="#main"
      className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-2 focus:z-50 focus:rounded-control focus:bg-spruce-green focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-warm-ivory focus:shadow-pop"
    >
      Skip to content
    </a>
  );
}
