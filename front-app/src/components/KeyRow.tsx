import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, Pencil, Trash2 } from "lucide-react";

import { deleteKey, KeyPresence, Provider, putKey } from "../api/keys";


const LABELS: Record<Provider, string> = {
  openai: "OpenAI",
  anthropic: "Anthropic",
  google: "Google (Gemini)",
};


export function KeyRow({
  provider,
  presence,
}: {
  provider: Provider;
  presence: KeyPresence | undefined;
}) {
  const qc = useQueryClient();
  const [editing, setEditing] = useState(!presence);
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);

  const putMut = useMutation({
    mutationFn: (v: string) => putKey(provider, v),
    onSuccess: () => {
      setValue("");
      setEditing(false);
      setError(null);
      qc.invalidateQueries({ queryKey: ["me", "keys"] });
    },
    onError: (e) => setError(e instanceof Error ? e.message : "save failed"),
  });
  const delMut = useMutation({
    mutationFn: () => deleteKey(provider),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["me", "keys"] });
      setEditing(true);
    },
  });

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!value) {
      setError("Enter a value or click Cancel.");
      return;
    }
    putMut.mutate(value);
  }

  return (
    <div className="rounded border border-border bg-card p-4">
      <div className="mb-2 flex items-center justify-between gap-2">
        <div>
          <div className="text-sm font-medium">{LABELS[provider]}</div>
          {presence && !editing && (
            <div className="text-xs text-muted-foreground">
              Set · updated {new Date(presence.updated_at).toLocaleString()}
            </div>
          )}
          {!presence && !editing && (
            <div className="text-xs text-muted-foreground">Not set</div>
          )}
        </div>

        {presence && !editing && (
          <div className="flex items-center gap-1">
            <button
              onClick={() => {
                setEditing(true);
                setError(null);
              }}
              title="Replace key"
              className="rounded p-1.5 text-muted-foreground hover:bg-muted"
            >
              <Pencil className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={() => delMut.mutate()}
              disabled={delMut.isPending}
              title="Clear key"
              className="rounded p-1.5 text-muted-foreground hover:bg-muted disabled:opacity-50"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </div>

      {editing && (
        <form onSubmit={onSubmit} className="flex items-center gap-2">
          <input
            type="password"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="Paste the key…"
            autoComplete="off"
            spellCheck={false}
            className="flex-1 rounded border border-input bg-background px-3 py-1.5 text-sm focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
          />
          <button
            type="submit"
            disabled={putMut.isPending}
            className="rounded bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {putMut.isPending ? "Saving…" : <Check className="h-3.5 w-3.5" />}
          </button>
          {presence && (
            <button
              type="button"
              onClick={() => {
                setEditing(false);
                setError(null);
                setValue("");
              }}
              className="rounded px-3 py-1.5 text-sm text-muted-foreground hover:bg-muted"
            >
              Cancel
            </button>
          )}
        </form>
      )}

      {error && (
        <div className="mt-2 text-xs text-destructive">{error}</div>
      )}
    </div>
  );
}
