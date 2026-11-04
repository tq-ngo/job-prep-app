import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import LoginPage from "@/app/(auth)/login/page";

vi.mock("@/context/AuthContext", () => ({
  useAuth: () => ({ completeLogin: vi.fn() }),
}));

async function renderPage(params: { next?: string; error?: string }) {
  render(await LoginPage({ searchParams: Promise.resolve(params) }));
}

describe("LoginPage (src/app/(auth)/login/page.tsx)", () => {
  it("explains why Google sign-in was refused for an existing account", async () => {
    await renderPage({ error: "account_exists" });
    expect(screen.getByRole("alert")).toHaveTextContent(/already exists/i);
  });

  it("shows nothing for unknown error codes instead of echoing them", async () => {
    await renderPage({ error: "<script>alert(1)</script>" });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("falls back to /jobs for off-site next values", async () => {
    await renderPage({ next: "//evil.com" });
    expect(screen.getByRole("link", { name: /Continue with Google/i })).toHaveAttribute(
      "href",
      expect.stringContaining("next=%2Fjobs"),
    );
  });
});
