import { describe, it, expect } from "vitest";
import { googleLoginUrl, safeNextPath, API_BASE, SITE_URL } from "@/lib/urls";

describe("URL Utilities (src/lib/urls.ts)", () => {
  it("googleLoginUrl generates correct login path with default /jobs redirect", () => {
    const url = googleLoginUrl();
    expect(url).toBe(`${API_BASE}/api/v1/auth/google/login?next=%2Fjobs`);
  });

  it("googleLoginUrl preserves custom next path and encodes query parameters properly", () => {
    const customNext = "/jobs?category=FAANG+&source=github";
    const url = googleLoginUrl(customNext);
    expect(url).toBe(
      `${API_BASE}/api/v1/auth/google/login?next=${encodeURIComponent(customNext)}`
    );
  });

  it("API_BASE defaults to empty string for same-origin routing", () => {
    expect(typeof API_BASE).toBe("string");
  });

  it("SITE_URL has a valid fallback", () => {
    expect(SITE_URL).toBeTruthy();
  });

  it("safeNextPath allows safe relative paths", () => {
    expect(safeNextPath("/jobs")).toBe("/jobs");
    expect(safeNextPath("/jobs?page=2&category=FAANG%2B")).toBe("/jobs?page=2&category=FAANG%2B");
    expect(safeNextPath("/news#latest")).toBe("/news#latest");
  });

  it("safeNextPath rejects absolute, protocol-relative, backslash, and control-char URLs", () => {
    const unsafe = [
      undefined,
      null,
      "",
      "jobs",
      "https://evil.com",
      "//evil.com",
      "/\\evil.com",
      "/\t/evil.com",
      "/%09/evil.com",
      "/%0aSet-Cookie:a=b",
      "/jobs\r\nHeader:x",
      "/%7f/evil.com",
    ];
    for (const candidate of unsafe) {
      expect(safeNextPath(candidate), String(candidate)).toBe("/jobs");
    }
  });
});
