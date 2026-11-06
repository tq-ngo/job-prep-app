import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import LoginForm from "@/app/(auth)/login/LoginForm";
import { authApi } from "@/lib/api";
import { NETWORK_ERROR, RATE_LIMITED } from "@/lib/errors";
import { useAuth } from "@/context/AuthContext";

vi.mock("@/context/AuthContext", () => ({
  useAuth: vi.fn(),
}));

describe("LoginForm (src/app/(auth)/login/LoginForm.tsx)", () => {
  const mockCompleteLogin = vi.fn();

  beforeEach(() => {
    vi.restoreAllMocks();
    vi.mocked(useAuth).mockReturnValue({
      user: null,
      isLoading: false,
      completeLogin: mockCompleteLogin,
      logout: vi.fn(),
      refreshUser: vi.fn(),
    });
  });

  async function submit(nextPath = "/jobs") {
    const user = userEvent.setup();
    render(<LoginForm nextPath={nextPath} />);
    await user.type(screen.getByLabelText("Email"), "applicant@stanford.edu");
    await user.type(screen.getByLabelText("Password"), "SecurePassword123!");
    await user.click(screen.getByRole("button", { name: /Sign In/i }));
    return user;
  }

  it("renders labelled fields with autofill hints, and the Google link", () => {
    render(<LoginForm nextPath="/jobs" />);
    expect(screen.getByLabelText("Email")).toHaveAttribute("autocomplete", "email");
    expect(screen.getByLabelText("Password")).toHaveAttribute("autocomplete", "current-password");
    expect(screen.getByRole("link", { name: /Continue with Google/i })).toHaveAttribute("href", expect.stringContaining("next=%2Fjobs"));
  });

  it("shows and hides the password", async () => {
    const user = userEvent.setup();
    render(<LoginForm nextPath="/jobs" />);
    const password = screen.getByLabelText("Password");
    const toggle = screen.getByRole("button", { name: "Show password" });

    expect(password).toHaveAttribute("type", "password");
    await user.click(toggle);
    expect(password).toHaveAttribute("type", "text");
    expect(toggle).toHaveAttribute("aria-pressed", "true");
    await user.click(toggle);
    expect(password).toHaveAttribute("type", "password");
  });

  it("signs in and continues to nextPath", async () => {
    const loginSpy = vi.spyOn(authApi, "login").mockResolvedValueOnce({ status: "success", csrf_token: "c" });
    await submit("/jobs?category=Quant");
    expect(loginSpy).toHaveBeenCalledWith("applicant@stanford.edu", "SecurePassword123!");
    await waitFor(() => expect(mockCompleteLogin).toHaveBeenCalledWith("/jobs?category=Quant"));
  });

  it.each([
    [{ response: { status: 401, data: { detail: "Incorrect email or password" } } }, "Incorrect email or password."],
    [{ response: { status: 429 } }, RATE_LIMITED],
    [{ request: {}, code: "ERR_NETWORK" }, NETWORK_ERROR],
    [{ response: { status: 500, data: { detail: "Traceback: db down" } } }, "Sign-in failed. Please try again."],
  ])("tells apart why sign-in failed (%#)", async (error, message) => {
    vi.spyOn(authApi, "login").mockRejectedValueOnce(error);
    await submit();
    expect(await screen.findByRole("alert")).toHaveTextContent(message);
    expect(mockCompleteLogin).not.toHaveBeenCalled();
  });

  it("shows a notice (e.g. after registering) as status, not as an error", () => {
    render(<LoginForm nextPath="/jobs" notice="Account created. Sign in to continue." />);
    expect(screen.getByRole("status")).toHaveTextContent("Account created");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("carries nextPath to the registration link", () => {
    render(<LoginForm nextPath="/news" />);
    expect(screen.getByRole("link", { name: "Create one" })).toHaveAttribute("href", "/register?next=%2Fnews");
  });
});
