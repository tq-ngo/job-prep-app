import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import DashboardNavbar from "@/components/DashboardNavbar";
import { useAuth } from "@/context/AuthContext";
import { ThemeProvider } from "@/context/ThemeContext";
import { authApi } from "@/lib/api";

vi.mock("@/context/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/jobs",
}));

function renderNavbar() {
  return render(
    <ThemeProvider>
      <DashboardNavbar />
    </ThemeProvider>
  );
}

describe("DashboardNavbar Component (src/components/DashboardNavbar.tsx)", () => {
  const mockLogout = vi.fn();
  const mockRefreshUser = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders active route highlighting and user skills pills", () => {
    vi.mocked(useAuth).mockReturnValue({
      user: {
        id: 1,
        email: "student@mit.edu",
        skills: ["React", "Go"],
      },
      isLoading: false,
      completeLogin: vi.fn(),
      logout: mockLogout,
      refreshUser: mockRefreshUser,
    });

    renderNavbar();

    expect(screen.getByText("JobPrep")).toBeInTheDocument();
    expect(screen.getByText("Jobs")).toBeInTheDocument();
    expect(screen.getByText("News")).toBeInTheDocument();

    // Skills
    expect(screen.getByText("React")).toBeInTheDocument();
    expect(screen.getByText("Go")).toBeInTheDocument();
    expect(screen.getByText("student@mit.edu")).toBeInTheDocument();
  });

  it("adds a new skill when typing and pressing Enter", async () => {
    const updateSkillsSpy = vi.spyOn(authApi, "updateSkills").mockResolvedValueOnce({
      id: 1,
      email: "student@mit.edu",
      skills: ["React", "Go", "Docker"],
    });

    vi.mocked(useAuth).mockReturnValue({
      user: {
        id: 1,
        email: "student@mit.edu",
        skills: ["React", "Go"],
      },
      isLoading: false,
      completeLogin: vi.fn(),
      logout: mockLogout,
      refreshUser: mockRefreshUser,
    });

    const user = userEvent.setup();
    renderNavbar();

    // Click "+ Edit" button to enter editing mode
    const editBtn = screen.getByRole("button", { name: /\+ Edit/i });
    await user.click(editBtn);

    const input = screen.getByPlaceholderText(/New skill\.\.\./i);
    await user.type(input, "Docker{Enter}");

    expect(updateSkillsSpy).toHaveBeenCalledWith(["React", "Go", "Docker"]);
    expect(mockRefreshUser).toHaveBeenCalled();
  });

  it("removes a skill when clicking the remove button in edit mode", async () => {
    const updateSkillsSpy = vi.spyOn(authApi, "updateSkills").mockResolvedValueOnce({
      id: 1,
      email: "student@mit.edu",
      skills: ["Go"],
    });

    vi.mocked(useAuth).mockReturnValue({
      user: {
        id: 1,
        email: "student@mit.edu",
        skills: ["React", "Go"],
      },
      isLoading: false,
      completeLogin: vi.fn(),
      logout: mockLogout,
      refreshUser: mockRefreshUser,
    });

    const user = userEvent.setup();
    renderNavbar();

    // Enter edit mode first
    const editBtn = screen.getByRole("button", { name: /\+ Edit/i });
    await user.click(editBtn);

    // Find the skill pill for React and click its remove button
    const reactPill = screen.getByText("React").closest("span");
    const removeBtn = reactPill!.querySelector("button");
    expect(removeBtn).toBeInTheDocument();
    await user.click(removeBtn!);

    expect(updateSkillsSpy).toHaveBeenCalledWith(["Go"]);
    expect(mockRefreshUser).toHaveBeenCalled();
  });

  it("calls logout when Sign Out button is clicked", async () => {
    vi.mocked(useAuth).mockReturnValue({
      user: {
        id: 1,
        email: "student@mit.edu",
        skills: [],
      },
      isLoading: false,
      completeLogin: vi.fn(),
      logout: mockLogout,
      refreshUser: mockRefreshUser,
    });

    const user = userEvent.setup();
    renderNavbar();

    const signOutBtn = screen.getByRole("button", { name: /Sign out/i });
    await user.click(signOutBtn);

    expect(mockLogout).toHaveBeenCalledTimes(1);
  });
});
