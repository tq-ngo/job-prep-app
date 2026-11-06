"use client";

import { useState } from "react";
import Link from "next/link";
import { authApi } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";
import { useAuth } from "@/context/AuthContext";
import Alert from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import Field from "@/components/ui/Field";
import { Input, PasswordInput } from "@/components/ui/Input";
import AuthCard from "../AuthCard";
import GoogleSignIn from "../GoogleSignIn";

export default function LoginForm({
  nextPath,
  initialError = "",
  notice = "",
}: {
  nextPath: string;
  initialError?: string;
  /** Informational message, e.g. after registering or a session ending. */
  notice?: string;
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
      // The server sets HttpOnly cookies; no token comes back in the body.
      await authApi.login(email, password);
      await completeLogin(nextPath);
    } catch (err) {
      // Every failure used to read "Invalid credentials", including being
      // rate limited or offline, which sent people retyping a correct password.
      setError(
        apiErrorMessage(err, {
          byStatus: { 401: "Incorrect email or password." },
          fallback: "Sign-in failed. Please try again.",
        }),
      );
    } finally {
      setIsLoading(false);
    }
  };

  const registerHref = nextPath === "/jobs" ? "/register" : `/register?next=${encodeURIComponent(nextPath)}`;

  return (
    <AuthCard
      title="Welcome back"
      subtitle="Sign in to your JobPrep account"
      footer={
        <>
          Don&apos;t have an account?{" "}
          <Link href={registerHref} className="text-spruce-green hover:text-spruce-green-hover font-medium">
            Create one
          </Link>
        </>
      }
    >
      {notice && !error && <Alert className="mb-6">{notice}</Alert>}

      <GoogleSignIn nextPath={nextPath} />

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
          <PasswordInput autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </Field>
        <Button type="submit" size="lg" block loading={isLoading}>
          {isLoading ? "Signing in..." : "Sign In"}
        </Button>
      </form>
    </AuthCard>
  );
}
