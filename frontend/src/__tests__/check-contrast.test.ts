import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import path from "node:path";

describe("WCAG 2.1 Contrast Tokens (src/app/globals.css)", () => {
  const cssPath = path.resolve(__dirname, "../app/globals.css");
  const css = readFileSync(cssPath, "utf8");

  function extractTokens(selector: string): Record<string, string> {
    const block = css.match(new RegExp(`${selector}\\s*\\{([^}]*)\\}`))?.[1] ?? "";
    return Object.fromEntries(
      [...block.matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{6})/g)].map((m) => [m[1], m[2]])
    );
  }

  const luminance = (hex: string) => {
    const [r, g, b] = [1, 3, 5].map((i) => {
      const c = parseInt(hex.slice(i, i + 2), 16) / 255;
      return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };

  const ratio = (a: string, b: string) => {
    const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
    return (hi + 0.05) / (lo + 0.05);
  };

  const PAIRS: [string, string, number][] = [
    ["foreground", "background", 4.5],
    ["foreground-heading", "background", 4.5],
    ["foreground-muted", "background", 4.5],
    ["foreground-subtle", "background", 4.5],
    ["foreground-subtle", "neutral-soft", 4.5],
    ["spruce-green", "background", 4.5],
    ["amber-clay", "background", 4.5],
    ["background", "spruce-green", 4.5],
  ];

  const light = extractTokens(":root");
  const dark = { ...light, ...extractTokens("\\.dark") };

  it.each([
    ["light", light],
    ["dark", dark],
  ])("verifies all core text pairs exceed 4.5:1 ratio in %s theme", (themeName, themeTokens) => {
    for (const [fg, bg, min] of PAIRS) {
      expect(themeTokens[fg], `Missing token --${fg} in ${themeName}`).toBeDefined();
      expect(themeTokens[bg], `Missing token --${bg} in ${themeName}`).toBeDefined();
      const r = ratio(themeTokens[fg], themeTokens[bg]);
      expect(
        r,
        `${themeName}: ${fg} on ${bg} (${themeTokens[fg]} on ${themeTokens[bg]}) ratio ${r.toFixed(2)} is below ${min}:1`
      ).toBeGreaterThanOrEqual(min);
    }
  });
});

