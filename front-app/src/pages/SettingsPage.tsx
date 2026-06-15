import { useMutation } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { updateMe } from "../api/auth";
import { useAuth } from "../auth/AuthContext";

/**
 * Settings — display profile.
 *
 * `role` is a free-text optional string forwarded to hexgate-wrapped agents
 * as `context.user.role`. HexUI never interprets it; the dev team picks the
 * vocabulary in their hexgate policy.
 *
 * Provider API keys are NOT configured here — the agent backend reads its own
 * keys from its environment (see the backend's `.env`). HexUI never holds them.
 */
export function SettingsPage() {
  const { user, setUser } = useAuth();

  const [name, setName] = useState(user?.name ?? "");
  const [role, setRole] = useState(user?.role ?? "");

  // Re-sync local form state if the auth-context user object changes
  // (e.g. after revalidation on mount).
  useEffect(() => {
    setName(user?.name ?? "");
    setRole(user?.role ?? "");
  }, [user?.name, user?.role]);

  const profileMutation = useMutation({
    mutationFn: () => updateMe({ name: name || null, role: role || null }),
    onSuccess: (updated) => setUser(updated),
  });

  const dirty =
    (name || "") !== (user?.name ?? "") || (role || "") !== (user?.role ?? "");

  return (
    <div className="mx-auto h-full max-w-2xl overflow-auto p-8">
      <h1 className="mb-1 text-lg font-semibold tracking-tight">Settings</h1>
      <p className="mb-8 text-sm text-muted-foreground">
        Your display name and optional hexgate role. Provider API keys live in
        the agent backend's environment — HexUI never holds them.
      </p>

      <section className="mb-8">
        <h2 className="mb-3 text-xs font-medium uppercase tracking-wider text-muted-foreground">
          Profile
        </h2>
        <form
          className="space-y-4 rounded-lg border border-border bg-card p-4 text-sm"
          onSubmit={(e) => {
            e.preventDefault();
            profileMutation.mutate();
          }}
        >
          <div>
            <div className="text-muted-foreground">Signed in as</div>
            <div>{user?.email ?? "—"}</div>
          </div>
          <div>
            <label className="mb-1 block text-muted-foreground" htmlFor="name">
              Display name
            </label>
            <input
              id="name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Your name"
              className="w-full rounded-md border border-border bg-background px-3 py-2"
            />
          </div>
          <div>
            <label className="mb-1 block text-muted-foreground" htmlFor="role">
              Role <span className="text-xs">(optional)</span>
            </label>
            <input
              id="role"
              type="text"
              value={role}
              onChange={(e) => setRole(e.target.value)}
              placeholder="e.g. billing, support, admin"
              className="w-full rounded-md border border-border bg-background px-3 py-2"
            />
            <p className="mt-1 text-xs text-muted-foreground">
              Forwarded to hexgate-wrapped agents for per-call policy decisions.
              Leave blank if your agent doesn't use hexgate.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={!dirty || profileMutation.isPending}
              className="rounded-md bg-primary px-3 py-1.5 text-primary-foreground disabled:cursor-not-allowed disabled:opacity-50"
            >
              {profileMutation.isPending ? "Saving…" : "Save"}
            </button>
            {profileMutation.isSuccess && !dirty && (
              <span className="text-xs text-muted-foreground">Saved</span>
            )}
            {profileMutation.isError && (
              <span className="text-xs text-destructive">
                {(profileMutation.error as Error).message}
              </span>
            )}
          </div>
        </form>
      </section>
    </div>
  );
}
