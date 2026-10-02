"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
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

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  const fetchUser = useCallback(async () => {
    try {
      setUser(await authApi.getMe());
    } catch {
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    // Tokens live in HttpOnly cookies now, so the client cannot inspect them
    // to decide whether a session exists — it simply asks the server. The old
    // `localStorage.getItem("access_token")` precheck is gone along with the
    // XSS-readable token it was reading.
    void fetchUser();
  }, [fetchUser]);

  const completeLogin = useCallback(
    async (next = "/jobs") => {
      await fetchUser();
      router.replace(next);
      router.refresh(); // re-run server components now that the cookie is set
    },
    [fetchUser, router],
  );

  const logout = useCallback(async () => {
    try {
      // Server-side revocation: denylists both tokens and clears the cookies.
      // Previously "logout" only deleted a localStorage key, leaving the token
      // valid for its full lifetime if it had already been exfiltrated.
      await authApi.logout();
    } finally {
      setUser(null);
      router.replace("/login");
      router.refresh();
    }
  }, [router]);

  return (
    <AuthContext.Provider
      value={{ user, isLoading, completeLogin, logout, refreshUser: fetchUser }}
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
