import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { NextRequest } from "next/server";
import { proxy, PATHNAME_HEADER, SESSION_INVALID_REASON } from "@/proxy";

const TEST_SECRET = "super-secure-jwt-secret-key-at-least-32-chars-long";

async function makeToken(
  payload: Record<string, unknown>,
  secret = TEST_SECRET,
  alg = "HS256"
): Promise<string> {
  const now = Math.floor(Date.now() / 1000);
  const fullPayload = {
    sub: "user@example.com",
    jti: "test-jti-1",
    iat: now - 10,
    ...payload,
  };
  const encoder = new TextEncoder();
  const header = { alg, typ: "JWT" };
  const b64 = (obj: unknown) => Buffer.from(JSON.stringify(obj)).toString("base64url");
  const unsigned = `${b64(header)}.${b64(fullPayload)}`;

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

async function makeRawToken(
  payload: Record<string, unknown>,
  secret = TEST_SECRET,
  alg = "HS256"
): Promise<string> {
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
  return `${unsigned}.${Buffer.from(signature).toString("base64url")}`;
}

describe("Edge Route Proxy (src/proxy.ts)", () => {
  beforeEach(() => {
    vi.stubEnv("JWT_SECRET", TEST_SECRET);
    vi.stubEnv("NODE_ENV", "production");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("passes through valid access token on protected route and strips _rsc from x-app-pathname", async () => {
    const now = Math.floor(Date.now() / 1000);
    const token = await makeToken({
      typ: "access",
      iss: "job-prep-app",
      aud: "job-prep-app:api",
      exp: now + 3600,
    });

    const req = new NextRequest("http://localhost:3000/jobs?page=2&_rsc=abc123", {
      headers: { cookie: `access_token=${token}` },
    });

    const res = await proxy(req);
    expect(res.status).toBe(200);
    expect(res.headers.get("location")).toBeNull();
    expect(res.headers.get(`x-middleware-request-${PATHNAME_HEADER}`)).toBe("/jobs?page=2");
  });

  it("redirects unauthenticated user without session hint directly to /login with no-store headers", async () => {
    const req = new NextRequest("http://localhost:3000/jobs?_rsc=xyz", {
      headers: {},
    });

    const res = await proxy(req);
    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toContain("/login?next=%2Fjobs");
    expect(res.headers.get("location")).not.toContain("_rsc");
    expect(res.headers.get("cache-control")).toBe("private, no-store");
    expect(res.headers.get("vary")).toBe("Cookie");
  });

  it("redirects expired (or <5s remaining) access token with csrf hint to /resume with Secure cookie over HTTPS", async () => {
    const now = Math.floor(Date.now() / 1000);
    const almostExpired = await makeToken({
      typ: "access",
      iss: "job-prep-app",
      aud: "job-prep-app:api",
      exp: now + 3, // inside 5s expiry buffer
    });

    const req = new NextRequest("http://localhost:3000/jobs", {
      headers: {
        cookie: `access_token=${almostExpired}; csrf_token=some-csrf-hint`,
        "x-forwarded-proto": "https",
      },
    });

    const res = await proxy(req);
    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toContain("/api/v1/auth/resume?next=%2Fjobs");
    const guard = res.cookies.get("auth_resume_attempt");
    expect(guard?.value).toBe("1");
    expect(guard?.secure).toBe(true);
    expect(res.headers.get("cache-control")).toBe("private, no-store");
  });

  it("breaks resume loop if auth_resume_attempt is already set and redirects to /login", async () => {
    const req = new NextRequest("http://localhost:3000/jobs", {
      headers: { cookie: `csrf_token=some-csrf-hint; auth_resume_attempt=1` },
    });

    const res = await proxy(req);
    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toContain("/login?next=%2Fjobs");
  });

  it("returns 204 No Content for router prefetch even without csrf_token (including Sec-Purpose)", async () => {
    const cases: Record<string, string>[] = [
      { cookie: "csrf_token=some-csrf-hint", "next-router-prefetch": "1" },
      { "sec-purpose": "prefetch" },
    ];
    for (const headers of cases) {
      const req = new NextRequest("http://localhost:3000/jobs", { headers });
      const res = await proxy(req);
      expect(res.status).toBe(204);
      expect(res.headers.get("cache-control")).toBe("private, no-store");
    }
  });

  it("rejects forged alg 'none', wrong typ, future nbf, or missing sub/jti/iat claims", async () => {
    const now = Math.floor(Date.now() / 1000);
    const invalidTokens = [
      await makeToken({ typ: "access", iss: "job-prep-app", aud: "job-prep-app:api", exp: now + 3600 }, TEST_SECRET, "none"),
      await makeToken({ typ: "refresh", iss: "job-prep-app", aud: "job-prep-app:api", exp: now + 3600 }),
      await makeToken({ typ: "access", iss: "job-prep-app", aud: "job-prep-app:api", exp: now + 3600, nbf: now + 120 }),
      await makeRawToken({ typ: "access", iss: "job-prep-app", aud: "job-prep-app:api", exp: now + 3600 }),
    ];

    for (const token of invalidTokens) {
      const req = new NextRequest("http://localhost:3000/jobs", {
        headers: { cookie: `access_token=${token}` },
      });
      const res = await proxy(req);
      expect(res.status).toBe(307);
      expect(res.headers.get("location")).toContain("/login");
    }
  });

  it("handles JWT_SECRET rotation without stale cached CryptoKey", async () => {
    const now = Math.floor(Date.now() / 1000);
    const otherSecret = "another-super-secure-secret-key-at-least-32-chars";
    vi.stubEnv("JWT_SECRET", otherSecret);
    const token = await makeToken(
      { typ: "access", iss: "job-prep-app", aud: "job-prep-app:api", exp: now + 3600 },
      otherSecret
    );
    const req = new NextRequest("http://localhost:3000/jobs", {
      headers: { cookie: `access_token=${token}` },
    });
    const res = await proxy(req);
    expect(res.status).toBe(200);
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

  it("treats only whole /login and /register segments as auth pages and strips inbound x-app-pathname", async () => {
    const now = Math.floor(Date.now() / 1000);
    const token = await makeToken({ typ: "access", iss: "job-prep-app", aud: "job-prep-app:api", exp: now + 3600 });
    for (const path of ["/login-help", "/registered"]) {
      const res = await proxy(
        new NextRequest(`http://localhost:3000${path}`, {
          headers: { cookie: `access_token=${token}`, [PATHNAME_HEADER]: "//evil.com" },
        })
      );
      expect(res.headers.get("location"), path).toBeNull();
      expect(res.headers.get(`x-middleware-request-${PATHNAME_HEADER}`)).toBeNull();
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
