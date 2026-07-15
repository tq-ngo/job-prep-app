"use client";

import { useState } from "react";
import { authApi } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import Link from "next/link";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const { login } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError("");
    try {
      const data = await authApi.login(email, password);
      await login(data.access_token);
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
        <p className="text-slate-ink/60 text-center mb-8 text-sm">Sign in to your JobPrep account</p>
        
        {error && (
          <div className="bg-amber-clay/10 border border-amber-clay/30 text-amber-clay text-sm px-4 py-3 rounded mb-6">
            {error}
          </div>
        )}
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-ink/70 mb-1.5">Email</label>
            <input 
              type="email" value={email} onChange={e => setEmail(e.target.value)} 
              className="w-full bg-background border border-slate-soft rounded px-4 py-3 text-slate-ink focus:outline-none focus:ring-1 focus:ring-spruce-green text-sm transition-all" 
              required 
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-ink/70 mb-1.5">Password</label>
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
        
        <p className="mt-6 text-center text-sm text-slate-ink/60">
          Don&apos;t have an account?{" "}
          <Link href="/register" className="text-spruce-green hover:text-spruce-green-hover font-medium">Create one</Link>
        </p>
      </div>
    </div>
  );
}
