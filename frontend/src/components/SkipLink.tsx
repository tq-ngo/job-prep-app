/**
 * First focusable element on the page: lets keyboard and screen-reader
 * users jump past the navigation to `#main`. Hidden until focused.
 */
export default function SkipLink() {
  return (
    <a
      href="#main"
      className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-2 focus:z-50 focus:rounded-full focus:bg-primary focus:px-4 focus:py-2 focus:text-label-large focus:font-medium focus:text-on-primary focus:shadow-level-3"
    >
      Skip to content
    </a>
  );
}
