import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import path from "node:path";
import { PAIRS, composite, evaluate, ratio } from "../../scripts/contrast-pairs.mjs";

const css = readFileSync(path.resolve(__dirname, "../app/globals.css"), "utf8");

describe("WCAG 2.1 contrast tokens (src/app/globals.css)", () => {
  const results = evaluate(css);

  it.each(["light", "dark"])("every pair meets its minimum in the %s theme", (theme) => {
    const failures = results
      .filter((r) => r.theme === theme && !r.ok)
      .map((r) =>
        r.missing
          ? `missing token --${r.missing}`
          : `${r.fg} on ${r.bg}: ${r.ratio.toFixed(2)} < ${r.min}`,
      );
    expect(failures).toEqual([]);
  });

  it("checks every pair in both themes", () => {
    expect(results).toHaveLength(PAIRS.length * 2);
  });

  it("matches published WCAG reference ratios", () => {
    expect(ratio("#000000", "#ffffff")).toBeCloseTo(21, 5);
    expect(ratio("#777777", "#ffffff")).toBeCloseTo(4.48, 2);
  });

  it("composites translucent tints over the surface", () => {
    expect(composite("#000000", 0.5, "#ffffff")).toBe("#808080");
    expect(composite("#b45309", 0, "#faf9f5")).toBe("#faf9f5");
  });

  it("would catch a failing tint pair", () => {
    // Plain amber-clay on its own 10% tint is the pair that used to fail.
    const [light] = evaluate(css, [["amber-clay", "amber-clay/10", 4.5]]);
    expect(light.ok).toBe(false);
  });

  it("keeps the dark-mode text hierarchy ordered", () => {
    const dark = results.filter((r) => r.theme === "dark" && r.bg === "background");
    const get = (fg: string) => dark.find((r) => r.fg === fg)!.ratio;
    expect(get("foreground-heading")).toBeGreaterThan(get("foreground"));
    expect(get("foreground")).toBeGreaterThan(get("foreground-muted"));
    expect(get("foreground-muted")).toBeGreaterThan(get("foreground-subtle"));
  });
});
