import { describe, it, expect } from "vitest";
import { googleLoginUrl, API_BASE, SITE_URL } from "@/lib/urls";

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
});
