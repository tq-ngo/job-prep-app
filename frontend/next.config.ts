import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  // Fix Turbopack workspace root detection warning
  turbopack: {
    root: path.resolve(__dirname),
  },

  // Standalone output for production Docker builds
  output: "standalone",
};

export default nextConfig;
