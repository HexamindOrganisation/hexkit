import { useQuery } from "@tanstack/react-query";

import { KeyPresence, listKeys, PROVIDERS } from "../api/keys";
import { useAuth } from "../auth/AuthContext";
import { KeyRow } from "../components/KeyRow";


export function SettingsPage() {
  const { user } = useAuth();
  const keys = useQuery({ queryKey: ["me", "keys"], queryFn: listKeys });

  const byProvider = new Map<string, KeyPresence>(
    (keys.data ?? []).map((k) => [k.provider, k]),
  );

  return (
    <div className="mx-auto max-w-2xl p-8">
      <h1 className="mb-1 text-lg font-semibold tracking-tight">Settings</h1>
      <p className="mb-8 text-sm text-muted-foreground">
        Per-user API keys are stored encrypted on the server and never
        returned in responses.
      </p>

      <section className="mb-8">
        <h2 className="mb-3 text-sm font-medium uppercase tracking-wider text-muted-foreground">
          Profile
        </h2>
        <div className="rounded border border-border bg-card p-4 text-sm">
          <div className="text-muted-foreground">Email</div>
          <div>{user?.email ?? "—"}</div>
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-sm font-medium uppercase tracking-wider text-muted-foreground">
          API keys
        </h2>
        {keys.isLoading && (
          <div className="text-sm text-muted-foreground">Loading…</div>
        )}
        {keys.isError && (
          <div className="rounded border border-destructive/40 bg-destructive/10 p-3 text-sm">
            Couldn't load keys: {(keys.error as Error).message}
          </div>
        )}
        {!keys.isLoading && !keys.isError && (
          <div className="space-y-3">
            {PROVIDERS.map((p) => (
              <KeyRow key={p} provider={p} presence={byProvider.get(p)} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
