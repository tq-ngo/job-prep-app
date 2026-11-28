import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import ProtectedLayout from "@/app/(app)/layout";

let cookieMap: Record<string, string> = { access_token: "abc" };
let mockPathname = "/news";

vi.mock("next/headers", () => ({
  cookies: async () => ({
    toString: () =>
      Object.entries(cookieMap)
        .map(([k, v]) => `${k}=${v}`)
        .join("; "),
    has: (name: string) => name in cookieMap,
  }),
  headers: async () => new Headers({ "x-app-pathname": mockPathname }),
}));

const redirect = vi.fn((url: string) => {
  throw new Error(`NEXT_REDIRECT ${url}`);
});
vi.mock("next/navigation", () => ({
  redirect: (url: string) => redirect(url),
  usePathname: () => "/news",
  useRouter: () => ({ replace: vi.fn(), refresh: vi.fn(), push: vi.fn() }),
}));
vi.mock("@/components/DashboardNavbar", () => ({ default: () => <nav aria-label="Main" /> }));

afterEach(() => {
  vi.unstubAllGlobals();
  redirect.mockClear();
  cookieMap = { access_token: "abc" };
  mockPathname = "/news";
});

describe("(app) layout", () => {
  it("redirects a revoked session without csrf hint to /login, keeping safe next and reason", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 401 })));
    await expect(ProtectedLayout({ children: <p>secret</p> })).rejects.toThrow("NEXT_REDIRECT");
    expect(redirect).toHaveBeenCalledWith("/login?next=%2Fnews&reason=session_invalid");
  });

  it("routes a 401 with csrf_token (and no resume guard) through /api/v1/auth/resume first", async () => {
    cookieMap = { access_token: "expired", csrf_token: "hint" };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 401 })));
    await expect(ProtectedLayout({ children: <p>secret</p> })).rejects.toThrow("NEXT_REDIRECT");
    expect(redirect).toHaveBeenCalledWith("/api/v1/auth/resume?next=%2Fnews");
  });

  it("sanitizes unsafe x-app-pathname headers before redirecting", async () => {
    mockPathname = "//evil.com";
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 401 })));
    await expect(ProtectedLayout({ children: <p>secret</p> })).rejects.toThrow("NEXT_REDIRECT");
    expect(redirect).toHaveBeenCalledWith("/login?next=%2Fjobs&reason=session_invalid");
  });

  it("redirects without calling the API when there are no cookies", async () => {
    cookieMap = {};
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
    await expect(ProtectedLayout({ children: null })).rejects.toThrow("NEXT_REDIRECT");
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("renders the shell with a skip link to main content for a valid session", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(Response.json({ id: 1, email: "a@b.c", skills: [] })),
    );
    const ui = await ProtectedLayout({ children: <p>dashboard</p> });
    render(<QueryClientProvider client={new QueryClient()}>{ui}</QueryClientProvider>);

    const skip = screen.getByRole("link", { name: "Skip to content" });
    expect(skip).toHaveAttribute("href", "#main");
    expect(screen.getByRole("main")).toHaveAttribute("id", "main");
    expect(screen.getByText("dashboard")).toBeInTheDocument();
    expect(redirect).not.toHaveBeenCalled();
  });

  it("fails closed without rendering protected children when the API is unreachable or returns 503", async () => {
    for (const stub of [
      vi.fn().mockRejectedValue(new Error("ECONNREFUSED")),
      vi.fn().mockResolvedValue(new Response(null, { status: 503 })),
    ]) {
      vi.stubGlobal("fetch", stub);
      const ui = await ProtectedLayout({ children: <p>secret-dashboard</p> });
      const { unmount } = render(<QueryClientProvider client={new QueryClient()}>{ui}</QueryClientProvider>);
      expect(screen.queryByText("secret-dashboard")).not.toBeInTheDocument();
      expect(screen.getByText(/Service temporarily unavailable/i)).toBeInTheDocument();
      unmount();
    }
  });
});
