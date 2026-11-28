import type { NextConfig } from "next";
import path from "path";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL || "http://localhost:8000";
const ENABLE_API_REWRITES =
  process.env.NODE_ENV === "development" || process.env.ENABLE_API_REWRITES === "true";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["127.0.0.1", "127.0.0.1:3000", "localhost", "localhost:3000"],
  poweredByHeader: false,

  turbopack: {
    root: path.resolve(__dirname),
  },

  output: "standalone",
  skipTrailingSlashRedirect: true,

  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
        ],
      },
    ];
  },

  async rewrites() {
    // Only proxy /api/* through Next in local dev (or explicit opt-in).
    // In production, nginx is the sole /api/ edge so :3000 cannot be used
    // as an unthrottled bypass around nginx limits, Host checks, or headers.
    if (!ENABLE_API_REWRITES) {
      return [];
    }
    return [
      { source: "/api/:path*/", destination: `${INTERNAL_API_URL}/api/:path*/` },
      { source: "/api/:path*", destination: `${INTERNAL_API_URL}/api/:path*` },
    ];
  },
};

export default nextConfig;
