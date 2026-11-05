"use client";

import { useState } from "react";
import { authApi } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import Link from "next/link";
import AuthCard from "../AuthCard";
import Alert from "@/components/ui/Alert";
import { Button, ButtonLink } from "@/components/ui/Button";
import Field from "@/components/ui/Field";
import GoogleIcon from "@/components/ui/GoogleIcon";
import { Input } from "@/components/ui/Input";

export default function LoginForm({
  nextPath,
  initialError = "",
}: {
  nextPath: string;
  initialError?: string;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(initialError);
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
    <AuthCard
      title="Welcome back"
      subtitle="Sign in to your JobPrep account"
      footer={
        <>
          Don&apos;t have an account?{" "}
          <Link href="/register" className="text-spruce-green hover:text-spruce-green-hover font-medium">Create one</Link>
        </>
      }
    >
      <ButtonLink
        href={authApi.googleLoginUrl(nextPath)}
        native
        variant="secondary"
        size="lg"
        block
        icon={<GoogleIcon />}
        className="mb-6"
      >
        Continue with Google
      </ButtonLink>

      <div className="flex items-center gap-3 mb-6">
        <span className="h-px flex-1 bg-slate-soft" />
        <span className="text-xs text-foreground-muted">or</span>
        <span className="h-px flex-1 bg-slate-soft" />
      </div>

      {error && (
        <Alert variant="error" className="mb-6">
          {error}
        </Alert>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <Field label="Email">
          <Input type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </Field>
        <Field label="Password">
          <Input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </Field>
        <Button type="submit" size="lg" block loading={isLoading}>
          {isLoading ? "Signing in..." : "Sign In"}
        </Button>
      </form>
    </AuthCard>
  );
}
