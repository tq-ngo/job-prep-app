import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import RegisterForm from "@/app/(auth)/register/RegisterForm";
import RegisterPage from "@/app/(auth)/register/page";
import { authApi } from "@/lib/api";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

async function fillAndSubmit() {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Email"), "new@example.com");
  await user.type(screen.getByLabelText("Password"), "Passw0rdOK");
  await user.click(screen.getByRole("button", { name: "Create Account" }));
}

describe("Registration", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    push.mockClear();
  });

  it("labels its fields, describes the password rules and offers Google", () => {
    render(<RegisterForm nextPath="/jobs" />);
    const password = screen.getByLabelText("Password");
    expect(password).toHaveAttribute("autocomplete", "new-password");
    expect(password).toHaveAccessibleDescription(/uppercase letter/);
    expect(screen.getByRole("link", { name: /continue with google/i })).toBeInTheDocument();
  });

  it("sends people to sign in with a confirmation, keeping where they were going", async () => {
    vi.spyOn(authApi, "register").mockResolvedValue({ id: 1, email: "new@example.com", skills: [] });
    render(<RegisterForm nextPath="/news" />);
    await fillAndSubmit();
    await waitFor(() => expect(push).toHaveBeenCalledWith("/login?registered=1&next=%2Fnews"));
  });

  it("shows the server's reason when registration is refused", async () => {
    vi.spyOn(authApi, "register").mockRejectedValue({ response: { status: 400, data: { detail: "Email already registered" } } });
    render(<RegisterForm nextPath="/jobs" />);
    await fillAndSubmit();
    expect(await screen.findByRole("alert")).toHaveTextContent("Email already registered");
    expect(push).not.toHaveBeenCalled();
  });

  it("ignores an off-site next value", async () => {
    render(await RegisterPage({ searchParams: Promise.resolve({ next: "//evil.com" }) }));
    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/login");
  });
});
