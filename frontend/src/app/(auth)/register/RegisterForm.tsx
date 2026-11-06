"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { authApi } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";
import Alert from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import Field from "@/components/ui/Field";
import { Input, PasswordInput } from "@/components/ui/Input";
import AuthCard from "../AuthCard";
import GoogleSignIn from "../GoogleSignIn";

export default function RegisterForm({ nextPath }: { nextPath: string }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const router = useRouter();

  const withNext = (path: string, extra = "") => {
    const params = new URLSearchParams(extra);
    if (nextPath !== "/jobs") params.set("next", nextPath);
    const qs = params.toString();
    return qs ? `${path}?${qs}` : path;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError("");
    try {
      await authApi.register(email, password);
      // On to sign-in, keeping where the user was headed, with a confirmation.
      router.push(withNext("/login", "registered=1"));
    } catch (err) {
      // 400 "Email already registered" and the password rules (422) come
      // back as readable details.
      setError(apiErrorMessage(err, { fallback: "Registration failed. Please try again." }));
      setIsLoading(false);
    }
  };

  return (
    <AuthCard
      title="Create Account"
      subtitle="Join JobPrep to track job listings"
      footer={
        <>
          Already have an account?{" "}
          <Link href={withNext("/login")} className="text-spruce-green hover:text-spruce-green-hover font-medium">
            Sign in
          </Link>
        </>
      }
    >
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
        <Field label="Password" hint="At least 8 characters, with an uppercase letter, a lowercase letter and a digit.">
          <PasswordInput
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={8}
            required
          />
        </Field>
        <Button type="submit" size="lg" block loading={isLoading}>
          {isLoading ? "Creating account..." : "Create Account"}
        </Button>
      </form>
    </AuthCard>
  );
}
