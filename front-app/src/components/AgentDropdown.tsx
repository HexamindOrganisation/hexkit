import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Check, ChevronDown, Search } from "lucide-react";

import { AgentMetadata, listAgents } from "../api/agents";


export function useAgentsQuery() {
  return useQuery({ queryKey: ["agents"], queryFn: listAgents });
}


/**
 * Searchable agent picker for the header.
 *
 * When `value` is set, it's shown (and `disabled` may lock the dropdown to
 * read-only display for the per-conversation header). On `/`, the host
 * passes the current `?agent=` value and `onChange` updates the URL.
 */
export function AgentDropdown({
  value,
  onChange,
  disabled = false,
}: {
  value: string | null;
  onChange: (agentId: string) => void;
  disabled?: boolean;
}) {
  const agents = useAgentsQuery();
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const selected = useMemo<AgentMetadata | undefined>(
    () => agents.data?.find((a) => a.agent_id === value),
    [agents.data, value],
  );

  const filtered = useMemo(() => {
    const list = agents.data ?? [];
    if (!filter.trim()) return list;
    const q = filter.toLowerCase();
    return list.filter(
      (a) =>
        a.agent_id.toLowerCase().includes(q) ||
        a.name.toLowerCase().includes(q) ||
        a.framework.toLowerCase().includes(q),
    );
  }, [agents.data, filter]);

  const label =
    selected?.name ??
    (value
      ? value
      : agents.isLoading
      ? "Loading agents…"
      : (agents.data?.length ?? 0) === 0
      ? "No agents loaded"
      : "Pick an agent");

  return (
    <div ref={ref} className="relative">
      <button
        disabled={disabled || (agents.data?.length ?? 0) === 0}
        onClick={() => setOpen((o) => !o)}
        className="flex h-8 items-center gap-2 rounded border border-border bg-background px-2.5 text-sm hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
      >
        <span className="truncate">{label}</span>
        {!disabled && <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />}
      </button>
      {open && (
        <div className="absolute left-0 z-20 mt-2 w-72 rounded-md border border-border bg-popover shadow-md">
          <div className="flex items-center gap-2 border-b border-border px-3 py-2">
            <Search className="h-3.5 w-3.5 text-muted-foreground" />
            <input
              autoFocus
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Search agents…"
              className="w-full bg-transparent text-sm focus:outline-none"
            />
          </div>
          <div className="max-h-72 overflow-y-auto py-1">
            {filtered.length === 0 ? (
              <div className="px-3 py-2 text-xs text-muted-foreground">
                No agents match "{filter}".
              </div>
            ) : (
              filtered.map((a) => (
                <button
                  key={a.agent_id}
                  onClick={() => {
                    onChange(a.agent_id);
                    setOpen(false);
                    setFilter("");
                  }}
                  className="flex w-full items-start gap-2 px-3 py-2 text-left hover:bg-muted"
                >
                  {a.agent_id === value ? (
                    <Check className="mt-0.5 h-3.5 w-3.5 text-primary" />
                  ) : (
                    <span className="mt-0.5 h-3.5 w-3.5" />
                  )}
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium">{a.name}</div>
                    <div className="truncate text-xs text-muted-foreground">
                      {a.framework} · {a.agent_id}
                    </div>
                  </div>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
