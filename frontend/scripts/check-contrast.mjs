#!/usr/bin/env node
// WCAG 2.1 contrast check for the colour tokens in src/app/globals.css.
// Run: npm run check:contrast  (exits 1 if any pair is below its minimum)
import { readFileSync } from "node:fs";

const css = readFileSync(new URL("../src/app/globals.css", import.meta.url), "utf8");

function tokens(selector) {
  const block = css.match(new RegExp(`${selector}\\s*\\{([^}]*)\\}`))?.[1] ?? "";
  return Object.fromEntries([...block.matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{6})/g)].map((m) => [m[1], m[2]]));
}

const luminance = (hex) => {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const ratio = (a, b) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};

// [foreground token, background token, minimum ratio]
const PAIRS = [
  ["foreground", "background", 4.5],
  ["foreground-heading", "background", 4.5],
  ["foreground-muted", "background", 4.5],
  ["foreground-subtle", "background", 4.5],
  ["foreground-subtle", "neutral-soft", 4.5],
  ["spruce-green", "background", 4.5],
  ["amber-clay", "background", 4.5],
  ["background", "spruce-green", 4.5], // button label on a green button
];

const light = tokens(":root");
const dark = { ...light, ...tokens("\\.dark") };
let failed = false;
for (const [theme, t] of [["light", light], ["dark", dark]]) {
  for (const [fg, bg, min] of PAIRS) {
    if (!t[fg] || !t[bg]) {
      console.error(`✗ ${theme}: missing token --${!t[fg] ? fg : bg}`);
      failed = true;
      continue;
    }
    const r = ratio(t[fg], t[bg]);
    const ok = r >= min;
    failed ||= !ok;
    console.log(`${ok ? "✓" : "✗"} ${theme.padEnd(5)} ${fg.padEnd(19)} on ${bg.padEnd(13)} ${r.toFixed(2)}:1 (min ${min})`);
  }
}
process.exit(failed ? 1 : 0);
