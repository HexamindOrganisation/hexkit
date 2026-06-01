import { useQuery } from "@tanstack/react-query";

import { KeyPresence, listKeys, PROVIDERS } from "../api/keys";
import { KeyRow } from "../components/KeyRow";

/**
 * Settings — per-user API keys (single-user). Keys are stored encrypted on the
 * server (Fernet) and never returned. Setting an OpenAI key here lets the proxy
 * forward it to the agent backend so the `probe` agent can call a real LLM.
 */
export function SettingsPage() {
  const keys = useQuery({ queryKey: ["me", "keys"], queryFn: listKeys });

  const byProvider = new Map<string, KeyPresence>(
    (keys.data ?? []).map((k) => [k.provider, k]),
  );

  return (
    <div className="mx-auto h-full max-w-2xl overflow-auto p-8">
      <h1 className="mb-1 text-lg font-semibold tracking-tight">Settings</h1>
      <p className="mb-8 text-sm text-muted-foreground">
        Per-user API keys are stored encrypted on the server and never returned
        in responses. Set your OpenAI key to chat with a real model.
      </p>

      <section className="mb-8">
        <h2 className="mb-3 text-xs font-medium uppercase tracking-wider text-muted-foreground">
          Profile
        </h2>
        <div className="rounded-lg border border-border bg-card p-4 text-sm">
          <div className="text-muted-foreground">Signed in as</div>
          <div>dev01@hexamind.ai</div>
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-xs font-medium uppercase tracking-wider text-muted-foreground">
          API keys
        </h2>
        {keys.isLoading && (
          <div className="text-sm text-muted-foreground">Loading…</div>
        )}
        {keys.isError && (
          <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm">
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
