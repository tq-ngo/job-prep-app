import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { NextRequest } from "next/server";
import { proxy, SESSION_INVALID_REASON } from "@/proxy";

const TEST_SECRET = "super-secure-jwt-secret-key-at-least-32-chars-long";

async function makeToken(payload: Record<string, unknown>, secret = TEST_SECRET, alg = "HS256"): Promise<string> {
  const encoder = new TextEncoder();
  const header = { alg, typ: "JWT" };
  const b64 = (obj: unknown) => Buffer.from(JSON.stringify(obj)).toString("base64url");
  const unsigned = `${b64(header)}.${b64(payload)}`;

  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const signature = await crypto.subtle.sign("HMAC", key, encoder.encode(unsigned));
  const sigB64 = Buffer.from(signature).toString("base64url");
  return `${unsigned}.${sigB64}`;
}

describe("Edge Route Proxy (src/proxy.ts)", () => {
  beforeEach(() => {
    vi.stubEnv("JWT_SECRET", TEST_SECRET);
    vi.stubEnv("NODE_ENV", "production");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("passes through valid access token on protected route and injects pathname header", async () => {
    const now = Math.floor(Date.now() / 1000);
    const token = await makeToken({
      typ: "access",
      iss: "job-prep-app",
      aud: "job-prep-app:api",
      exp: now + 3600,
    });

    const req = new NextRequest("http://localhost:3000/jobs?page=2", {
      headers: { cookie: `access_token=${token}` },
    });

    const res = await proxy(req);
    expect(res.status).toBe(200);
    expect(res.headers.get("location")).toBeNull();
  });

  it("redirects unauthenticated user without session hint directly to /login", async () => {
    const req = new NextRequest("http://localhost:3000/jobs", {
      headers: {},
    });

    const res = await proxy(req);
    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toContain("/login?next=%2Fjobs");
  });

  it("redirects expired access token with csrf session hint to /api/v1/auth/resume and sets resume guard cookie", async () => {
    const now = Math.floor(Date.now() / 1000);
    const expiredToken = await makeToken({
      typ: "access",
      iss: "job-prep-app",
      aud: "job-prep-app:api",
      exp: now - 100,
    });

    const req = new NextRequest("http://localhost:3000/jobs", {
      headers: { cookie: `access_token=${expiredToken}; csrf_token=some-csrf-hint` },
    });

    const res = await proxy(req);
    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toContain("/api/v1/auth/resume?next=%2Fjobs");
    expect(res.cookies.get("auth_resume_attempt")?.value).toBe("1");
  });

  it("breaks resume loop if auth_resume_attempt is already set and redirects to /login", async () => {
    const req = new NextRequest("http://localhost:3000/jobs", {
      headers: { cookie: `csrf_token=some-csrf-hint; auth_resume_attempt=1` },
    });

    const res = await proxy(req);
    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toContain("/login?next=%2Fjobs");
  });

  it("returns 204 No Content for router prefetch to avoid rotating refresh token on hover", async () => {
    const req = new NextRequest("http://localhost:3000/jobs", {
      headers: {
        cookie: `csrf_token=some-csrf-hint`,
        "next-router-prefetch": "1",
      },
    });

    const res = await proxy(req);
    expect(res.status).toBe(204);
  });

  it("rejects token with forged alg 'none'", async () => {
    const now = Math.floor(Date.now() / 1000);
    const token = await makeToken(
      {
        typ: "access",
        iss: "job-prep-app",
        aud: "job-prep-app:api",
        exp: now + 3600,
      },
      TEST_SECRET,
      "none"
    );

    const req = new NextRequest("http://localhost:3000/jobs", {
      headers: { cookie: `access_token=${token}` },
    });

    const res = await proxy(req);
    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toContain("/login");
  });

  it("redirects authenticated user away from /login to /jobs", async () => {
    const now = Math.floor(Date.now() / 1000);
    const token = await makeToken({
      typ: "access",
      iss: "job-prep-app",
      aud: "job-prep-app:api",
      exp: now + 3600,
    });

    const req = new NextRequest("http://localhost:3000/login", {
      headers: { cookie: `access_token=${token}` },
    });

    const res = await proxy(req);
    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toContain("/jobs");
  });

  it("treats only whole /login and /register segments as auth pages", async () => {
    const now = Math.floor(Date.now() / 1000);
    const token = await makeToken({ typ: "access", iss: "job-prep-app", aud: "job-prep-app:api", exp: now + 3600 });
    for (const path of ["/login-help", "/registered"]) {
      const res = await proxy(new NextRequest(`http://localhost:3000${path}`, { headers: { cookie: `access_token=${token}` } }));
      expect(res.headers.get("location"), path).toBeNull();
    }
  });

  it("clears access token on /login?reason=session_invalid instead of redirecting back to /jobs", async () => {
    const now = Math.floor(Date.now() / 1000);
    const token = await makeToken({
      typ: "access",
      iss: "job-prep-app",
      aud: "job-prep-app:api",
      exp: now + 3600,
    });

    const req = new NextRequest(
      `http://localhost:3000/login?reason=${SESSION_INVALID_REASON}`,
      {
        headers: { cookie: `access_token=${token}` },
      }
    );

    const res = await proxy(req);
    expect(res.headers.get("location")).toBeNull();
    expect(res.cookies.get("access_token")).toBeDefined();
  });

  it("fails closed in production if JWT_SECRET is unset", async () => {
    delete process.env.JWT_SECRET;
    delete process.env.SECRET_KEY;
    vi.stubEnv("NODE_ENV", "production");

    const now = Math.floor(Date.now() / 1000);
    const token = await makeToken({
      typ: "access",
      iss: "job-prep-app",
      aud: "job-prep-app:api",
      exp: now + 3600,
    });

    const req = new NextRequest("http://localhost:3000/jobs", {
      headers: { cookie: `access_token=${token}` },
    });

    const res = await proxy(req);
    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toContain("/login");
  });
});
