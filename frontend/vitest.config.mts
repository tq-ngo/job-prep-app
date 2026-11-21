import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

process.env.VITEST_SKIP_INSTALL_CHECKS = "1";

export default defineConfig({
  root: path.resolve(import.meta.dirname),
  server: {
    fs: {
      strict: true,
      allow: [path.resolve(import.meta.dirname)],
    },
  },
  plugins: [react()],
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/__tests__/**/*.{test,spec}.{ts,tsx}"],
  },
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
    },
  },
});
