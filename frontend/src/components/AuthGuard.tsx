"use client";

import { useAuth } from "@/context/AuthContext";
import { useRouter, usePathname } from "next/navigation";
import { useEffect } from "react";
import { Loader2 } from "lucide-react";

// Routes that don't require authentication
const PUBLIC_ROUTES = ["/login", "/register"];

export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  const isPublicRoute = PUBLIC_ROUTES.some((route) => pathname.startsWith(route));

  useEffect(() => {
    if (!isLoading && !user && !isPublicRoute) {
      router.replace("/login");
    }
    // If logged in and on login/register, redirect to /jobs
    if (!isLoading && user && isPublicRoute) {
      router.replace("/jobs");
    }
  }, [user, isLoading, isPublicRoute, router]);

  // Show loading spinner during initial token validation
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-4">
          <Loader2 size={24} className="animate-spin text-spruce-green" />
          <p className="font-mono text-xs text-slate-ink/40 uppercase tracking-widest">Loading...</p>
        </div>
      </div>
    );
  }

  // Don't render protected content if not authenticated
  if (!user && !isPublicRoute) {
    return null;
  }

  return <>{children}</>;
}
