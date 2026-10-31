import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import LoginForm from "@/app/(auth)/login/LoginForm";
import { authApi } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

vi.mock("@/context/AuthContext", () => ({
  useAuth: vi.fn(),
}));

describe("LoginForm Component (src/app/(auth)/login/LoginForm.tsx)", () => {
  const mockCompleteLogin = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useAuth).mockReturnValue({
      user: null,
      isLoading: false,
      completeLogin: mockCompleteLogin,
      logout: vi.fn(),
      refreshUser: vi.fn(),
    });
  });

  it("renders email, password inputs, submit button, and Google OAuth link", () => {
    render(<LoginForm nextPath="/jobs" />);

    expect(screen.getByLabelText(/Email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Password/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Sign In/i })).toBeInTheDocument();

    const googleLink = screen.getByRole("link", { name: /Continue with Google/i });
    expect(googleLink).toHaveAttribute("href", expect.stringContaining("next=%2Fjobs"));
  });

  it("submits valid credentials and calls completeLogin with nextPath", async () => {
    const loginSpy = vi.spyOn(authApi, "login").mockResolvedValueOnce({
      status: "success",
      csrf_token: "csrf-token-123",
    });

    const user = userEvent.setup();
    render(<LoginForm nextPath="/jobs?category=Quant" />);

    await user.type(screen.getByLabelText(/Email/i), "applicant@stanford.edu");
    await user.type(screen.getByLabelText(/Password/i), "SecurePassword123!");
    await user.click(screen.getByRole("button", { name: /Sign In/i }));

    expect(loginSpy).toHaveBeenCalledWith("applicant@stanford.edu", "SecurePassword123!");
    await waitFor(() => {
      expect(mockCompleteLogin).toHaveBeenCalledWith("/jobs?category=Quant");
    });
  });

  it("displays error message when login fails with 401", async () => {
    vi.spyOn(authApi, "login").mockRejectedValueOnce(new Error("Invalid credentials"));

    const user = userEvent.setup();
    render(<LoginForm nextPath="/jobs" />);

    await user.type(screen.getByLabelText(/Email/i), "wrong@stanford.edu");
    await user.type(screen.getByLabelText(/Password/i), "WrongPassword");
    await user.click(screen.getByRole("button", { name: /Sign In/i }));

    await waitFor(() => {
      expect(screen.getByText("Invalid credentials. Please try again.")).toBeInTheDocument();
    });
    expect(mockCompleteLogin).not.toHaveBeenCalled();
  });
});

