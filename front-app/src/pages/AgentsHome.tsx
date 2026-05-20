import { useEffect, useState } from "react";
import { AlertTriangle, ServerCrash } from "lucide-react";
import { listAgents } from "../runtime/api.js";
import type { AgentMetadata } from "../runtime/types.js";
import { AgentCard } from "../components/AgentCard.js";
import { PageHeader } from "../components/PageHeader.js";

type State =
  | { kind: "loading" }
  | { kind: "ready"; agents: AgentMetadata[] }
  | { kind: "error"; message: string };

export function AgentsHome(): JSX.Element {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    listAgents()
      .then((agents) => {
        if (!cancelled) setState({ kind: "ready", agents });
      })
      .catch((e: unknown) => {
        const message = e instanceof Error ? e.message : String(e);
        if (!cancelled) setState({ kind: "error", message });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const count = state.kind === "ready" ? state.agents.length : 0;

  return (
    <>
      <PageHeader
        title="Agents"
        subtitle={
          state.kind === "ready"
            ? `${count} agent${count === 1 ? "" : "s"} loaded by the runtime`
            : "Agents loaded by the runtime"
        }
      />
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-6xl px-6 py-6">
          {state.kind === "loading" && <SkeletonGrid />}
          {state.kind === "error" && <ErrorBanner message={state.message} />}
          {state.kind === "ready" && state.agents.length === 0 && (
            <EmptyState />
          )}
          {state.kind === "ready" && state.agents.length > 0 && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {state.agents.map((agent) => (
                <AgentCard key={agent.agent_id} agent={agent} />
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

function SkeletonGrid(): JSX.Element {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: 6 }).map((_, i) => (
        <div
          key={i}
          className="h-44 animate-pulse rounded-lg border border-border/60 bg-card/40"
        />
      ))}
    </div>
  );
}

function EmptyState(): JSX.Element {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center rounded-lg border border-dashed border-border bg-card/30 px-8 py-12 text-center">
      <span className="mb-3 grid h-10 w-10 place-items-center rounded-full bg-muted/40 text-muted-foreground ring-1 ring-inset ring-border">
        <AlertTriangle className="h-5 w-5" />
      </span>
      <p className="text-sm font-medium">No agents loaded</p>
      <p className="mt-1 text-xs text-muted-foreground">
        Check <code className="mono">PLATFORM_AGENTS_DIR</code> on the runtime
        and restart.
      </p>
    </div>
  );
}

function ErrorBanner({ message }: { message: string }): JSX.Element {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center rounded-lg border border-destructive/40 bg-destructive/10 px-8 py-10 text-center">
      <span className="mb-3 grid h-10 w-10 place-items-center rounded-full bg-destructive/15 text-destructive ring-1 ring-inset ring-destructive/30">
        <ServerCrash className="h-5 w-5" />
      </span>
      <p className="text-sm font-medium text-destructive">
        Could not reach the runtime
      </p>
      <pre className="mt-2 max-w-full overflow-x-auto whitespace-pre-wrap text-[11px] opacity-80">
        {message}
      </pre>
      <p className="mt-3 text-[11px] text-muted-foreground">
        Is the runtime running on <code className="mono">localhost:8080</code>?
        Set <code className="mono">PLATFORM_RUNTIME_URL</code> for a different
        host.
      </p>
    </div>
  );
}
