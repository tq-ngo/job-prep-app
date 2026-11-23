# JobPrep Frontend

The client application for JobPrep, built with Next.js 16 (App Router, Standalone), React 19, TypeScript 5, Tailwind CSS v4, and TanStack Query v5.

## Design System Architecture: Editorial-Modern + Material Design 3 Hybrid

JobPrep features an intentional hybrid design system that balances editorial publishing aesthetics with the structural rigour of Google Material Design 3 (M3):

- **Editorial Warmth**: Built on warm ivory (`#faf9f5`) and dark slate ink (`#141413`) paper palettes, human-readable editorial serif typography for headings (**Lora**), clean sans-serif UI typography (**Plus Jakarta Sans**), and monospace tokens (**Fira Code**).
- **Material Design 3 Primitives**: Implements M3 surface container hierarchies (`--neutral-soft` as container-low, `--surface-container`, `--surface-container-high`), tonal elevation shadows, full-pill status and filter chips, and Google Tech Blue accents (`#0b57d0` in light mode, `#8ab4f8` in dark mode).
- **Balanced Component Radii**: Controls (buttons, inputs, dropdowns) use `--radius-control` (8px / `0.5rem`) and cards/panels use `--radius-card` (12px / `0.75rem`), reserving full pills (`9999px`) for chips and badges.
- **Accessibility & Contrast**: 100% WCAG 2.1 AA compliant across all light and dark mode color pairs, automatically enforced at build time via `npm run check:contrast`.

## Key Architectural Patterns

1. **Edge Route Protection (`src/proxy.ts`)**: Next.js 16 edge proxy using Web Crypto HS256 to verify `access_token` and protect authenticated routes (`/jobs`, `/news`) without client-side redirects or layout flickers.
2. **URL-Synchronized Feed State**: Filter, search, pagination, and open job state are managed via `window.history` in `useJobFeedUrlState.ts`, preventing expensive SSR page re-renders on filter change.
3. **Responsive Split-Pane Navigation**: Desktop displays master-detail split pane with independent viewport scrolling. Mobile toggles cleanly between full list and full detail pane, with history-aware back navigation that preserves browsing context.
4. **Non-Intrusive Live Events**: SSE `created` events increment a floating `↑ N new jobs` button rather than jarringly prepending rows under active user scroll.

## Scripts & Testing

```bash
# Development server (proxies /api to INTERNAL_API_URL, default http://localhost:8000)
npm run dev

# Code quality checks
npm run lint
npx tsc --noEmit

# Unit & component tests (Vitest)
npm test

# WCAG 2.1 AA automated contrast audit
npm run check:contrast

# End-to-end smoke tests (Playwright)
npm run test:e2e

# Production build
npm run build
```
