import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import DashboardNavbar from "@/components/DashboardNavbar";
import { AuthProvider } from "@/context/AuthContext";
import { ThemeProvider } from "@/context/ThemeContext";
import { authApi, type User } from "@/lib/api";

let mockPathname = "/jobs";
vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname,
  useRouter: () => ({ replace: vi.fn(), refresh: vi.fn(), push: vi.fn() }),
}));

const user = (skills: string[] = ["react", "go"]): User => ({ id: 1, email: "student@mit.edu", skills });

function renderNavbar(initialUser: User | null = user()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <ThemeProvider>
        <AuthProvider initialUser={initialUser}>
          <DashboardNavbar />
        </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>,
  );
  return { client, ue: userEvent.setup() };
}

beforeEach(() => {
  mockPathname = "/jobs";
});
afterEach(() => {
  vi.restoreAllMocks();
});

describe("DashboardNavbar", () => {
  it("renders the brand link to home", () => {
    renderNavbar();
    const brand = screen.getByRole("link", { name: "JobPrep" });
    expect(brand).toHaveAttribute("href", "/");
  });

  it("marks the current page's link", () => {
    mockPathname = "/news/today";
    renderNavbar();
    const nav = screen.getByRole("navigation", { name: "Main" });
    expect(within(nav).getByRole("link", { name: /news/i })).toHaveAttribute("aria-current", "page");
    expect(within(nav).getByRole("link", { name: /jobs/i })).not.toHaveAttribute("aria-current");
  });

  it("marks jobs as current when on /jobs", () => {
    mockPathname = "/jobs";
    renderNavbar();
    const nav = screen.getByRole("navigation", { name: "Main" });
    expect(within(nav).getByRole("link", { name: /jobs/i })).toHaveAttribute("aria-current", "page");
    expect(within(nav).getByRole("link", { name: /news/i })).not.toHaveAttribute("aria-current");
  });

  it("toggles the mobile menu with its expanded state, and Escape closes it", async () => {
    const { ue } = renderNavbar();
    const menu = screen.getByRole("button", { name: "Menu" });
    expect(menu).toHaveAttribute("aria-expanded", "false");

    await ue.click(menu);
    expect(menu).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("navigation", { name: "Main menu" })).toBeInTheDocument();

    await ue.keyboard("{Escape}");
    expect(menu).toHaveAttribute("aria-expanded", "false");
    expect(menu).toHaveFocus();
  });

  it("displays the user email pill and signs out on click", async () => {
    const logout = vi.spyOn(authApi, "logout").mockResolvedValue();
    const { ue } = renderNavbar();
    expect(screen.getByText("student@mit.edu")).toBeInTheDocument();
    await ue.click(screen.getByRole("button", { name: "Sign out" }));
    expect(logout).toHaveBeenCalled();
  });

  it("offers Sign In when signed out", () => {
    renderNavbar(null);
    expect(screen.getByRole("link", { name: /sign in/i })).toHaveAttribute("href", "/login");
  });

  it("includes a theme toggle button", () => {
    renderNavbar();
    expect(screen.getByRole("button", { name: /dark mode|light mode/i })).toBeInTheDocument();
  });
});
