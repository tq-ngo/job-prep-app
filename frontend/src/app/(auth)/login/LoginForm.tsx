"use client";

import { useState } from "react";
import { authApi } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import Link from "next/link";

export default function LoginForm({ nextPath }: { nextPath: string }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const { completeLogin } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError("");
    try {
      // No token comes back in the body any more — the server sets HttpOnly
      // cookies. We just need to refresh the user and navigate.
      await authApi.login(email, password);
      await completeLogin(nextPath);
    } catch {
      setError("Invalid credentials. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4 font-sans">
      <div className="w-full max-w-sm bg-neutral-soft border border-slate-soft p-8 rounded">
        <h1 className="text-2xl font-serif font-medium text-slate-ink mb-2 text-center">Welcome back</h1>
        <p className="text-foreground-muted text-center mb-8 text-sm">Sign in to your JobPrep account</p>

        <a
          href={authApi.googleLoginUrl(nextPath)}
          className="flex items-center justify-center gap-3 w-full border border-slate-soft rounded px-4 py-3 mb-6 text-sm font-medium text-slate-ink hover:bg-slate-soft/30 transition-colors"
        >
          <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
            <path fill="#4285F4" d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62Z"/>
            <path fill="#34A853" d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.81.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.96v2.33A9 9 0 0 0 9 18Z"/>
            <path fill="#FBBC05" d="M3.97 10.72A5.41 5.41 0 0 1 3.68 9c0-.6.1-1.18.29-1.72V4.95H.96A9 9 0 0 0 0 9c0 1.45.35 2.82.96 4.05l3.01-2.33Z"/>
            <path fill="#EA4335" d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.59C13.46.89 11.43 0 9 0A9 9 0 0 0 .96 4.95l3.01 2.33C4.68 5.16 6.66 3.58 9 3.58Z"/>
          </svg>
          Continue with Google
        </a>

        <div className="flex items-center gap-3 mb-6">
          <span className="h-px flex-1 bg-slate-soft" />
          <span className="text-xs text-foreground-muted">or</span>
          <span className="h-px flex-1 bg-slate-soft" />
        </div>
        
        {error && (
          <div className="bg-amber-clay/10 border border-amber-clay/30 text-amber-clay text-sm px-4 py-3 rounded mb-6">
            {error}
          </div>
        )}
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-foreground mb-1.5">Email</label>
            <input 
              type="email" value={email} onChange={e => setEmail(e.target.value)} 
              className="w-full bg-background border border-slate-soft rounded px-4 py-3 text-slate-ink focus:outline-none focus:ring-1 focus:ring-spruce-green text-sm transition-all" 
              required 
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-foreground mb-1.5">Password</label>
            <input 
              type="password" value={password} onChange={e => setPassword(e.target.value)} 
              className="w-full bg-background border border-slate-soft rounded px-4 py-3 text-slate-ink focus:outline-none focus:ring-1 focus:ring-spruce-green text-sm transition-all" 
              required 
            />
          </div>
          <button 
            type="submit" 
            disabled={isLoading}
            className="w-full bg-spruce-green hover:bg-spruce-green-hover disabled:bg-slate-soft disabled:text-slate-ink/50 text-warm-ivory py-3 rounded font-medium transition-colors text-sm"
          >
            {isLoading ? "Signing in..." : "Sign In"}
          </button>
        </form>
        
        <p className="mt-6 text-center text-sm text-foreground-muted">
          Don&apos;t have an account?{" "}
          <Link href="/register" className="text-spruce-green hover:text-spruce-green-hover font-medium">Create one</Link>
        </p>
      </div>
    </div>
  );
}
