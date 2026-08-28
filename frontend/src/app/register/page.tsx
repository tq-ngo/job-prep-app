"use client";

import { useState } from "react";
import { authApi } from "@/lib/api";
import { useRouter } from "next/navigation";
import Link from "next/link";

export default function RegisterPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError("");
    try {
      await authApi.register(email, password);
      router.push("/login");
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      if (typeof detail === "string") {
        setError(detail);
      } else if (Array.isArray(detail)) {
        // Pydantic validation errors come as an array of objects with a "msg" field
        const messages = detail.map((d: any) => {
          const msg = d.msg || "";
          // Strip the "Value error, " prefix that Pydantic adds
          return msg.replace(/^Value error,\s*/i, "");
        });
        setError(messages.join(". "));
      } else {
        setError("Registration failed. Please try again.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4 font-sans">
      <div className="w-full max-w-sm bg-neutral-soft border border-slate-soft p-8 rounded">
        <h1 className="text-2xl font-serif font-medium text-slate-ink mb-2 text-center">Create Account</h1>
        <p className="text-slate-ink/60 text-center mb-8 text-sm">Join JobPrep to track job listings</p>
        
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
              minLength={6} required 
            />
          </div>
          <button 
            type="submit" 
            disabled={isLoading}
            className="w-full bg-spruce-green hover:bg-spruce-green-hover disabled:bg-slate-soft disabled:text-slate-ink/50 text-warm-ivory py-3 rounded font-medium transition-colors text-sm"
          >
            {isLoading ? "Creating account..." : "Create Account"}
          </button>
        </form>
        
        <p className="mt-6 text-center text-sm text-slate-ink/60">
          Already have an account?{" "}
          <Link href="/login" className="text-spruce-green hover:text-spruce-green-hover font-medium">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
