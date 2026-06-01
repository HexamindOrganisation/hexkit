import { FormEvent, useState } from "react";
import { Link, Navigate } from "react-router-dom";

import { HttpError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { AuthShell, Field } from "./LoginPage";


export function SignupPage() {
  const { token, signup } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (token) return <Navigate to="/" replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await signup({ email, password });
    } catch (err) {
      setError(
        err instanceof HttpError && err.status === 409
          ? "That email is already registered."
          : err instanceof Error
          ? err.message
          : "Signup failed.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthShell
      title="Create an account"
      subline={<>Already have one? <Link to="/login" className="underline">Sign in</Link>.</>}
    >
      <form onSubmit={onSubmit} className="space-y-4">
        <Field
          label="Email"
          type="email"
          value={email}
          onChange={setEmail}
          autoComplete="email"
          autoFocus
        />
        <Field
          label="Password (≥ 8 chars)"
          type="password"
          value={password}
          onChange={setPassword}
          autoComplete="new-password"
        />
        {error && (
          <div className="rounded border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive-foreground">
            {error}
          </div>
        )}
        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {submitting ? "Creating…" : "Create account"}
        </button>
      </form>
    </AuthShell>
  );
}
