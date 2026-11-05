// WCAG 2.1 contrast pairs for the colour tokens in src/app/globals.css.
// Shared by scripts/check-contrast.mjs (CI / `npm run check:contrast`) and
// src/__tests__/check-contrast.test.ts, so the two can't drift apart.

// Each pair: [foreground, background, minimum ratio].
// A colour is a CSS variable name from globals.css (not the utility name:
// `--border-soft`, not `slate-soft`), or "token/NN" for it at NN% opacity,
// alpha-composited over the surface it sits on (`background` unless the
// pair says `on`). That is how Tailwind's `bg-amber-clay/10` renders.
//   4.5 = text (1.4.3 AA)   3 = UI boundaries and focus rings (1.4.11)
export const PAIRS = [
  // Body text hierarchy
  ["foreground-heading", "background", 4.5],
  ["foreground", "background", 4.5],
  ["foreground-muted", "background", 4.5],
  ["foreground-subtle", "background", 4.5],
  ["foreground-muted", "neutral-soft", 4.5],
  ["foreground-subtle", "neutral-soft", 4.5],
  ["foreground-heading", "neutral-soft", 4.5],

  // Accents as text
  ["spruce-green", "background", 4.5],
  ["spruce-green", "neutral-soft", 4.5],
  ["spruce-green-hover", "background", 4.5],
  ["amber-clay", "background", 4.5],

  // Primary button label, at rest and hovered
  ["background", "spruce-green", 4.5],
  ["background", "spruce-green-hover", 4.5],

  // Tinted badges and alerts (Badge, Alert, selected toggles)
  ["spruce-green", "spruce-green/10", 4.5],
  ["amber-clay-on-tint", "amber-clay/10", 4.5],
  ["foreground-heading", "border-soft/40", 4.5], // ghost button hover (bg-slate-soft/40)

  // Job list rows: selected (bg-spruce-green/5) and hovered (bg-slate-soft/30)
  ["foreground-subtle", "spruce-green/5", 4.5],
  ["foreground-muted", "spruce-green/5", 4.5],
  ["foreground-subtle", "border-soft/30", 4.5],

  // Non-text: input borders and the focus ring must be visible (3:1)
  ["border-strong", "background", 3],
  ["border-strong", "neutral-soft", 3],
  ["focus-ring", "background", 3],
  ["focus-ring", "neutral-soft", 3],
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

/** Resolve "token" or "token/NN" to an opaque hex over `surface`. */
function resolve(tokens, ref, surface) {
  const [name, pct] = ref.split("/");
  const hex = tokens[name];
  if (!hex) return { missing: name };
  return { hex: pct ? composite(hex, Number(pct) / 100, surface) : hex };
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
      const surface = tokens.background;
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
