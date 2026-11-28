"use client";

import React, { createContext, useContext, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { authApi, User } from "@/lib/api";

export const AUTH_USER_QUERY_KEY = ["auth", "user"] as const;
const AUTH_CHANNEL_NAME = "jobprep-auth";

type AuthBroadcastMessage = { type: "logout" } | { type: "login" };

function postAuthBroadcast(msg: AuthBroadcastMessage): void {
  if (typeof BroadcastChannel === "undefined") return;
  try {
    const channel = new BroadcastChannel(AUTH_CHANNEL_NAME);
    channel.postMessage(msg);
    channel.close();
  } catch {
    // Ignore environments that restrict BroadcastChannel.
  }
}

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  completeLogin: (nextPath?: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: React.ReactNode;
  initialUser?: User | null;
}

export function AuthProvider({ children, initialUser }: AuthProviderProps) {
  const router = useRouter();
  const queryClient = useQueryClient();

  const hasInitialUser = initialUser !== undefined;
  const [initialDataUpdatedAt] = useState<number | undefined>(() =>
    hasInitialUser ? Date.now() : undefined,
  );

  const {
    data: user,
    isLoading,
    refetch,
  } = useQuery<User | null>({
    queryKey: AUTH_USER_QUERY_KEY,
    queryFn: async () => {
      try {
        return await authApi.getMe();
      } catch (err) {
        const status = (err as { response?: { status?: number } })?.response?.status;
        if (status === 401 || status === 403) {
          return null;
        }
        throw err;
      }
    },
    ...(hasInitialUser ? { initialData: initialUser, initialDataUpdatedAt } : {}),
    enabled: !hasInitialUser && (typeof window === "undefined" || authApi.hasSessionHint()),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  useEffect(() => {
    if (typeof BroadcastChannel === "undefined") return;
    let channel: BroadcastChannel | null = null;
    try {
      channel = new BroadcastChannel(AUTH_CHANNEL_NAME);
      channel.onmessage = (event: MessageEvent<AuthBroadcastMessage>) => {
        if (event.data?.type === "logout") {
          queryClient.setQueryData(AUTH_USER_QUERY_KEY, null);
          queryClient.removeQueries({ predicate: (q) => q.queryKey[0] !== "auth" });
          router.replace("/login");
          router.refresh();
        } else if (event.data?.type === "login") {
          queryClient.invalidateQueries({ queryKey: AUTH_USER_QUERY_KEY });
          router.refresh();
        }
      };
    } catch {
      return;
    }
    return () => {
      channel?.close();
    };
  }, [queryClient, router]);

  const refreshUser = useCallback(async () => {
    await refetch();
  }, [refetch]);

  const completeLogin = useCallback(
    async (nextPath = "/jobs") => {
      await queryClient.invalidateQueries({ queryKey: AUTH_USER_QUERY_KEY });
      await refetch();
      postAuthBroadcast({ type: "login" });
      router.replace(nextPath);
      router.refresh();
    },
    [queryClient, refetch, router],
  );

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      // Clear client state even if server logout fails
    }
    queryClient.setQueryData(AUTH_USER_QUERY_KEY, null);
    queryClient.removeQueries({ predicate: (q) => q.queryKey[0] !== "auth" });
    postAuthBroadcast({ type: "logout" });
    router.replace("/login");
    router.refresh();
  }, [queryClient, router]);

  return (
    <AuthContext.Provider
      value={{
        user: user ?? null,
        isLoading: !hasInitialUser && isLoading,
        completeLogin,
        logout,
        refreshUser,
      }}
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
