import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import DashboardNavbar from "@/components/DashboardNavbar";
import { AuthProvider, ME_QUERY_KEY } from "@/context/AuthContext";
import { ThemeProvider } from "@/context/ThemeContext";
import { authApi, type User } from "@/lib/api";

let mockPathname = "/jobs";
vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname,
  useRouter: () => ({ replace: vi.fn(), refresh: vi.fn(), push: vi.fn() }),
}));

const user = (skills: string[]): User => ({ id: 1, email: "student@mit.edu", skills });

function renderNavbar(initialUser: User | null = user(["react", "go"])) {
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

/** Deferred promise, to observe the optimistic state before the save settles. */
function deferred<T>() {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((res, rej) => ((resolve = res), (reject = rej)));
  return { promise, resolve, reject };
}

beforeEach(() => {
  mockPathname = "/jobs";
});
afterEach(() => {
  vi.restoreAllMocks();
});

const desktopSkills = () => screen.getAllByRole("list", { name: "Tracked skills" })[0];

describe("DashboardNavbar", () => {
  it("marks the current page's link", () => {
    mockPathname = "/news/today";
    renderNavbar();
    const nav = screen.getByRole("navigation", { name: "Main" });
    expect(within(nav).getByRole("link", { name: /news/i })).toHaveAttribute("aria-current", "page");
    expect(within(nav).getByRole("link", { name: /jobs/i })).not.toHaveAttribute("aria-current");
  });

  it("shows up to five skills and a count of the rest", () => {
    renderNavbar(user(["a", "b", "c", "d", "e", "f", "g"]));
    const list = desktopSkills();
    expect(within(list).getAllByText(/^[a-e]$/)).toHaveLength(5);
    expect(within(list).getByText("+2")).toBeInTheDocument();
  });

  it("opens the skills editor as a disclosure and closes it with Escape, restoring focus", async () => {
    const { ue } = renderNavbar();
    const edit = screen.getByRole("button", { name: "Edit" });
    expect(edit).toHaveAttribute("aria-expanded", "false");

    await ue.click(edit);
    expect(edit).toHaveAttribute("aria-expanded", "true");
    const panel = screen.getByRole("group", { name: "Edit tracked skills" });
    expect(within(panel).getByRole("textbox", { name: "Add a skill" })).toHaveFocus();

    await ue.keyboard("{Escape}");
    expect(screen.queryByRole("group", { name: "Edit tracked skills" })).not.toBeInTheDocument();
    expect(edit).toHaveFocus();
  });

  it("toggles the mobile menu with its expanded state, and Escape closes it", async () => {
    const { ue } = renderNavbar();
    const menu = screen.getByRole("button", { name: "Menu" });
    expect(menu).toHaveAttribute("aria-expanded", "false");

    await ue.click(menu);
    expect(menu).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("navigation", { name: "Main menu" })).toBeInTheDocument();
    // Skills are editable in the menu too (they used to be read-only there).
    expect(screen.getByRole("heading", { name: "Tracked skills" })).toBeInTheDocument();

    await ue.keyboard("{Escape}");
    expect(menu).toHaveAttribute("aria-expanded", "false");
    expect(menu).toHaveFocus();
  });

  it("signs out", async () => {
    const logout = vi.spyOn(authApi, "logout").mockResolvedValue();
    const { ue } = renderNavbar();
    await ue.click(screen.getByRole("button", { name: "Sign out" }));
    expect(logout).toHaveBeenCalled();
  });

  it("offers Sign In when signed out", () => {
    renderNavbar(null);
    expect(screen.getByRole("link", { name: /sign in/i })).toHaveAttribute("href", "/login");
  });
});

describe("SkillsEditor (via the navbar popover)", () => {
  async function openEditor(initial = user(["react", "go"])) {
    const r = renderNavbar(initial);
    await r.ue.click(screen.getByRole("button", { name: /^(edit|add skills)$/i }));
    const panel = screen.getByRole("group", { name: "Edit tracked skills" });
    return { ...r, panel };
  }

  it("adds a skill optimistically, then keeps the server's normalized list", async () => {
    const save = deferred<User>();
    const spy = vi.spyOn(authApi, "updateSkills").mockReturnValue(save.promise);
    const { ue, panel, client } = await openEditor();

    await ue.type(within(panel).getByRole("textbox", { name: "Add a skill" }), "Rust{Enter}");
    expect(spy).toHaveBeenCalledWith(["react", "go", "Rust"]);
    // Shown before the server answers.
    expect(within(panel).getByText("Rust")).toBeInTheDocument();

    save.resolve(user(["react", "go", "rust"]));
    await waitFor(() => expect(client.getQueryData<User>(ME_QUERY_KEY)?.skills).toEqual(["react", "go", "rust"]));
    expect(within(panel).getByRole("textbox", { name: "Add a skill" })).toHaveValue("");
  });

  it("rolls back and explains when a save fails", async () => {
    vi.spyOn(authApi, "updateSkills").mockRejectedValue({ response: { status: 500 } });
    const { ue, panel } = await openEditor();

    await ue.click(within(panel).getByRole("button", { name: "Remove go" }));

    expect(await within(panel).findByRole("alert")).toHaveTextContent("Couldn't save your skills");
    expect(within(panel).getByRole("button", { name: "Remove go" })).toBeInTheDocument();
  });

  it("removes any skill, not just the first five", async () => {
    const skills = ["a", "b", "c", "d", "e", "f", "g"];
    const spy = vi.spyOn(authApi, "updateSkills").mockImplementation(async (next) => user(next));
    const { ue, panel } = await openEditor(user(skills));

    await ue.click(within(panel).getByRole("button", { name: "Remove g" }));
    expect(spy).toHaveBeenCalledWith(["a", "b", "c", "d", "e", "f"]);
  });

  it("rejects duplicates (any case) and over-long skills without calling the API", async () => {
    const spy = vi.spyOn(authApi, "updateSkills");
    const { ue, panel } = await openEditor();
    const input = within(panel).getByRole("textbox", { name: "Add a skill" });

    await ue.type(input, "REACT{Enter}");
    expect(within(panel).getByRole("alert")).toHaveTextContent("already in your list");

    await ue.clear(input);
    await ue.type(input, `${"x".repeat(41)}{Enter}`);
    expect(within(panel).getByRole("alert")).toHaveTextContent("at most 40 characters");
    expect(spy).not.toHaveBeenCalled();
  });

  it("gives remove buttons a 24px target and an accessible name", async () => {
    const { panel } = await openEditor();
    const remove = within(panel).getByRole("button", { name: "Remove react" });
    expect(remove).toHaveClass("h-6", "w-6");
  });
});
