import type { NextConfig } from "next";
import path from "path";

// Where `/api/*` is forwarded when Next itself receives it. Under compose,
// nginx routes `/api/` to FastAPI before Next ever sees it, so this only
// matters for bare `npm run dev` on :3000 — it keeps that setup same-origin
// too, so the HttpOnly auth cookies land on the origin proxy.ts runs on.
const INTERNAL_API_URL = process.env.INTERNAL_API_URL || "http://localhost:8000";

const nextConfig: NextConfig = {
  // Fix Turbopack workspace root detection warning
  turbopack: {
    root: path.resolve(__dirname),
  },

  // Standalone output for production Docker builds
  output: "standalone",

  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${INTERNAL_API_URL}/api/:path*` },
    ];
  },
};

export default nextConfig;
