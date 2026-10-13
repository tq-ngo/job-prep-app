"use client";

import { createContext, useCallback, useContext } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { User, authApi } from "@/lib/api";
import { useRouter } from "next/navigation";

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  /** Called after a successful login; the server already set the cookies. */
  completeLogin: (next?: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const ME_QUERY_KEY = ["auth", "me"] as const;

/**
 * Session state, seeded from the server.
 *
 * `initialUser` comes from a server-side /auth/me in the layout, so the first
 * paint already knows who is signed in. The provider used to start with
 * `user = null` and fetch after hydration, so signed-in users saw a "Sign In"
 * button flash in the navbar on every page load.
 *
 *   initialUser = User | null  → trusted; no request on mount
 *   initialUser = undefined    → unknown (server fetch failed); fetch on mount
 */
export function AuthProvider({
  children,
  initialUser,
}: {
  children: React.ReactNode;
  initialUser?: User | null;
}) {
  const router = useRouter();
  const queryClient = useQueryClient();

  const { data, isPending, refetch } = useQuery({
    queryKey: ME_QUERY_KEY,
    queryFn: async () => {
      try {
        return await authApi.getMe();
      } catch {
        return null; // 401 after a failed refresh = signed out
      }
    },
    initialData: initialUser,
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  const refreshUser = useCallback(async () => {
    await refetch();
  }, [refetch]);

  const completeLogin = useCallback(
    async (next = "/jobs") => {
      await refetch();
      router.replace(next);
      router.refresh(); // re-run server components now that the cookie is set
    },
    [refetch, router],
  );

  const logout = useCallback(async () => {
    try {
      // Server-side revocation: denylists both tokens and the sign-in family,
      // then clears the cookies.
      await authApi.logout();
    } finally {
      // Drop every cached query, not just the user: the job and news caches
      // belong to the previous session.
      queryClient.clear();
      queryClient.setQueryData(ME_QUERY_KEY, null);
      router.replace("/login");
      router.refresh();
    }
  }, [queryClient, router]);

  return (
    <AuthContext.Provider
      value={{ user: data ?? null, isLoading: isPending, completeLogin, logout, refreshUser }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
