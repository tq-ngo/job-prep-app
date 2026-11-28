// WCAG 2.1 contrast pairs for the colour tokens in src/app/globals.css.
// Shared by scripts/check-contrast.mjs (CI / `npm run check:contrast`) and
// src/__tests__/check-contrast.test.ts, so the two can't drift apart.

// Each pair: [foreground, background, minimum ratio].
// A colour is a CSS variable name from globals.css, or "token/NN" for it at
// NN% opacity alpha-composited over `surface` (or "token/NN@base" over `base`).
//   4.5 = text (1.4.3 AA)   3 = UI boundaries and focus rings (1.4.11)
export const PAIRS = [
  // ── M3 On-Surface text hierarchy across all surface tiers ─────────────
  ["on-surface", "surface", 4.5],
  ["on-surface-variant", "surface", 4.5],
  ["on-surface", "surface-container-lowest", 4.5],
  ["on-surface-variant", "surface-container-lowest", 4.5],
  ["on-surface", "surface-container-low", 4.5],
  ["on-surface-variant", "surface-container-low", 4.5],
  ["on-surface", "surface-container-default", 4.5],
  ["on-surface-variant", "surface-container-default", 4.5],
  ["on-surface", "surface-container-high", 4.5],
  ["on-surface-variant", "surface-container-high", 4.5],
  ["on-surface", "surface-container-highest", 4.5],
  ["on-surface-variant", "surface-container-highest", 4.5],

  // ── M3 Primary links/accents on all surface tiers ─────────────────────
  ["primary", "surface", 4.5],
  ["primary", "surface-container-lowest", 4.5],
  ["primary", "surface-container-low", 4.5],
  ["primary", "surface-container-default", 4.5],
  ["primary", "surface-container-high", 4.5],
  ["primary", "surface-container-highest", 4.5],
  ["primary-hover", "surface", 4.5],
  ["primary-hover", "surface-container-low", 4.5],

  // ── M3 Filled & Tonal Container pairings ──────────────────────────────
  ["on-primary", "primary", 4.5],
  ["on-primary", "primary-hover", 4.5],
  ["on-primary-container", "primary-container", 4.5],
  ["on-secondary-container", "secondary-container", 4.5],
  ["on-surface", "secondary-container", 4.5],
  ["on-surface-variant", "secondary-container", 4.5],
  ["on-surface", "primary-container/35", 4.5],
  ["on-surface-variant", "primary-container/35", 4.5],
  ["on-error", "error", 4.5],
  ["on-error-container", "error-container", 4.5],
  ["error", "surface", 4.5],
  ["error", "surface-container-lowest", 4.5],
  ["error", "surface-container-low", 4.5],
  ["error", "surface-container-default", 4.5],

  // ── M3 State-layer overlays (hover 8%, focus-visible 12%) across tiers ─
  ["on-surface", "on-surface/8", 4.5],
  ["on-surface-variant", "on-surface/8", 4.5],
  ["on-surface", "on-surface/12", 4.5],
  ["on-surface-variant", "on-surface/12", 4.5],
  ["on-surface", "on-surface/8@surface-container-low", 4.5],
  ["on-surface-variant", "on-surface/8@surface-container-low", 4.5],
  ["on-surface", "on-surface/12@surface-container-low", 4.5],
  ["on-surface-variant", "on-surface/12@surface-container-low", 4.5],
  ["on-surface", "on-surface/8@surface-container-default", 4.5],
  ["on-surface-variant", "on-surface/8@surface-container-default", 4.5],
  ["on-primary-container", "on-primary-container/12@primary-container", 4.5],
  ["primary", "primary/8", 4.5],
  ["primary", "primary/12", 4.5],

  // ── M3 Non-text UI boundaries & focus rings (WCAG 1.4.11, 3:1) ────────
  ["outline", "surface", 3],
  ["outline", "surface-container-lowest", 3],
  ["outline", "surface-container-low", 3],
  ["outline", "surface-container-default", 3],
  ["outline", "surface-container-high", 3],
  ["outline", "surface-container-highest", 3],
  ["primary", "surface", 3],
  ["primary", "surface-container-low", 3],
  ["primary", "surface-container-default", 3],
];

/** `--name: #rrggbb` declarations inside the first `selector { ... }` block. */
export function parseTokens(css, selector) {
  const block = css.match(new RegExp(`${selector}\\s*\\{([^}]*)\\}`))?.[1] ?? "";
  return Object.fromEntries(
    [...block.matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{6})\b/g)].map((m) => [m[1], m[2].toLowerCase()]),
  );
}

const channels = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
const toHex = (rgb) => `#${rgb.map((c) => Math.round(c).toString(16).padStart(2, "0")).join("")}`;

export function luminance(hex) {
  const [r, g, b] = channels(hex).map((v) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function ratio(a, b) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

/** `top` at `alpha` (0-1) over an opaque `bottom`, as the browser blends it. */
export function composite(top, alpha, bottom) {
  const t = channels(top);
  const b = channels(bottom);
  return toHex(t.map((c, i) => c * alpha + b[i] * (1 - alpha)));
}

/** Resolve "token", "token/NN", or "token/NN@base" to an opaque hex. */
function resolve(tokens, ref, defaultSurface) {
  const [tokenPart, baseName] = ref.split("@");
  const [name, pct] = tokenPart.split("/");
  const hex = tokens[name];
  if (!hex) return { missing: name };
  if (!pct) return { hex };
  const baseHex = baseName ? tokens[baseName] : defaultSurface;
  if (!baseHex) return { missing: baseName ?? "surface" };
  return { hex: composite(hex, Number(pct) / 100, baseHex) };
}

/** Light and dark token maps; dark inherits anything it doesn't redefine. */
export function themes(css) {
  const light = parseTokens(css, ":root");
  return { light, dark: { ...light, ...parseTokens(css, "\\.dark") } };
}

/** Every pair in both themes: { theme, fg, bg, min, ratio, ok, missing? }. */
export function evaluate(css, pairs = PAIRS) {
  const results = [];
  for (const [theme, tokens] of Object.entries(themes(css))) {
    for (const [fg, bg, min] of pairs) {
      const surface = tokens.surface;
      const back = resolve(tokens, bg, surface);
      const front = back.hex ? resolve(tokens, fg, back.hex) : back;
      if (back.missing || front.missing) {
        results.push({ theme, fg, bg, min, ratio: 0, ok: false, missing: back.missing ?? front.missing });
        continue;
      }
      const r = ratio(front.hex, back.hex);
      results.push({ theme, fg, bg, min, ratio: r, ok: r >= min });
    }
  }
  return results;
}
