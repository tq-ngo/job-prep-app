#!/usr/bin/env node
// WCAG 2.1 contrast check for the colour tokens in src/app/globals.css.
// Run: npm run check:contrast  (exits 1 if any pair is below its minimum)
// The pairs live in ./contrast-pairs.mjs, shared with the unit test.
import { readFileSync } from "node:fs";
import { evaluate } from "./contrast-pairs.mjs";

const css = readFileSync(new URL("../src/app/globals.css", import.meta.url), "utf8");

let failed = false;
for (const { theme, fg, bg, min, ratio, ok, missing } of evaluate(css)) {
  failed ||= !ok;
  if (missing) {
    console.error(`✗ ${theme}: missing token --${missing}`);
    continue;
  }
  console.log(`${ok ? "✓" : "✗"} ${theme.padEnd(5)} ${fg.padEnd(19)} on ${bg.padEnd(18)} ${ratio.toFixed(2)}:1 (min ${min})`);
}
process.exit(failed ? 1 : 0);
