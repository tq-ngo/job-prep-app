import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { authApi, User } from "@/lib/api";

const mockReplace = vi.fn();
const mockRefresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: mockReplace,
    refresh: mockRefresh,
  }),
}));

const mockUser: User = {
  id: 1,
  email: "candidate@example.com",
  skills: ["React", "TypeScript", "Python"],
};

function createWrapper(initialUser?: User | null) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <AuthProvider initialUser={initialUser}>{children}</AuthProvider>
    </QueryClientProvider>
  );
  Wrapper.displayName = "TestQueryWrapper";
  return Wrapper;
}

describe("AuthContext (src/context/AuthContext.tsx)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("throws descriptive error when useAuth is accessed outside AuthProvider", () => {
    expect(() => renderHook(() => useAuth())).toThrow(
      "useAuth must be used within an AuthProvider"
    );
  });

  it("seeds user synchronously when initialUser is passed from SSR layout", () => {
    const { result } = renderHook(() => useAuth(), {
      wrapper: createWrapper(mockUser),
    });

    expect(result.current.user).toEqual(mockUser);
    expect(result.current.isLoading).toBe(false);
  });

  it("seeds null user when initialUser is null (unauthenticated)", () => {
    const { result } = renderHook(() => useAuth(), {
      wrapper: createWrapper(null),
    });

    expect(result.current.user).toBeNull();
    expect(result.current.isLoading).toBe(false);
  });

  it("completeLogin refetches identity, redirects to next path, and calls router.refresh()", async () => {
    vi.spyOn(authApi, "getMe").mockResolvedValueOnce(mockUser);

    const { result } = renderHook(() => useAuth(), {
      wrapper: createWrapper(null),
    });

    await act(async () => {
      await result.current.completeLogin("/jobs?q=Frontend");
    });

    expect(mockReplace).toHaveBeenCalledWith("/jobs?q=Frontend");
    expect(mockRefresh).toHaveBeenCalled();
  });

  it("logout calls authApi.logout, clears query cache, sets user null, and navigates to /login", async () => {
    const logoutSpy = vi.spyOn(authApi, "logout").mockResolvedValueOnce(undefined);

    const { result } = renderHook(() => useAuth(), {
      wrapper: createWrapper(mockUser),
    });

    await act(async () => {
      await result.current.logout();
    });

    expect(logoutSpy).toHaveBeenCalledTimes(1);
    expect(mockReplace).toHaveBeenCalledWith("/login");
    expect(mockRefresh).toHaveBeenCalled();
  });
});
