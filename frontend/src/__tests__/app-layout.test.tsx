import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import ProtectedLayout from "@/app/(app)/layout";

let cookieHeader = "access_token=abc";
vi.mock("next/headers", () => ({
  cookies: async () => ({ toString: () => cookieHeader }),
  headers: async () => new Headers({ "x-app-pathname": "/news" }),
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
  cookieHeader = "access_token=abc";
});

describe("(app) layout", () => {
  it("redirects a revoked session to /login, keeping the page and saying why", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 401 })));
    await expect(ProtectedLayout({ children: <p>secret</p> })).rejects.toThrow("NEXT_REDIRECT");
    expect(redirect).toHaveBeenCalledWith("/login?next=%2Fnews&reason=session_invalid");
  });

  it("redirects without calling the API when there are no cookies", async () => {
    cookieHeader = "";
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

  it("still renders when the API is unreachable (the client retries)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("ECONNREFUSED")));
    const ui = await ProtectedLayout({ children: <p>dashboard</p> });
    render(<QueryClientProvider client={new QueryClient()}>{ui}</QueryClientProvider>);
    expect(screen.getByText("dashboard")).toBeInTheDocument();
  });
});
