import { NextResponse } from "next/server";

/**
 * Lightweight internal container healthcheck endpoint for Next.js.
 * Keeps Docker HEALTHCHECK off the `/` marketing page and backend stats path.
 */
export function GET() {
  return NextResponse.json(
    { status: "ok" },
    {
      status: 200,
      headers: { "Cache-Control": "no-store" },
    },
  );
}
