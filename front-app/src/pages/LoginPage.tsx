import { FormEvent, useState } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";

import { HttpError } from "../api/client";
import { useAuth } from "../auth/AuthContext";


export function LoginPage() {
  const { token, login } = useAuth();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (token) {
    const dest = (location.state as { from?: { pathname?: string } })?.from
      ?.pathname;
    return <Navigate to={dest ?? "/"} replace />;
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login({ email, password });
    } catch (err) {
      setError(
        err instanceof HttpError && err.status === 401
          ? "Invalid email or password."
          : err instanceof Error
          ? err.message
          : "Login failed.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return <AuthShell title="Sign in" subline={<>New here? <Link to="/signup" className="underline">Create an account</Link>.</>}>
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
        label="Password"
        type="password"
        value={password}
        onChange={setPassword}
        autoComplete="current-password"
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
        {submitting ? "Signing in…" : "Sign in"}
      </button>
    </form>
  </AuthShell>;
}


// Shared shell + field — copied (not extracted) for now; if a third auth
// page lands we'll factor it out then.

export function AuthShell({
  title,
  subline,
  children,
}: {
  title: string;
  subline: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm rounded-lg border border-border bg-card p-8 shadow">
        <h1 className="mb-1 text-xl font-semibold tracking-tight">{title}</h1>
        <p className="mb-6 text-sm text-muted-foreground">{subline}</p>
        {children}
      </div>
    </main>
  );
}


export function Field({
  label,
  type,
  value,
  onChange,
  autoComplete,
  autoFocus,
}: {
  label: string;
  type: "email" | "password" | "text";
  value: string;
  onChange: (v: string) => void;
  autoComplete?: string;
  autoFocus?: boolean;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-muted-foreground">
        {label}
      </span>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete={autoComplete}
        autoFocus={autoFocus}
        required
        className="w-full rounded border border-input bg-background px-3 py-2 text-sm focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
      />
    </label>
  );
}
