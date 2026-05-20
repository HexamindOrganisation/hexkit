import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { AgentUI, type ActionDispatcher } from "agent-ui";
import { defaultChatPage } from "../config/defaultChatPage.js";
import { getMetadata, getUiYaml } from "../runtime/api.js";
import { RuntimeBridge } from "../runtime/runtimeBridge.js";
import type { AgentMetadata } from "../runtime/types.js";
import { FrameworkBadge } from "../components/FrameworkBadge.js";
import { HealthPill } from "../components/HealthPill.js";

type UiConfig = string | object;

type State =
  | { kind: "loading" }
  | {
      kind: "ready";
      metadata: AgentMetadata;
      ui: UiConfig;
      custom: boolean;
    }
  | { kind: "missing" }
  | { kind: "error"; message: string };

export function AgentChat(): JSX.Element {
  const { agentId } = useParams<{ agentId: string }>();
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    if (!agentId) return;
    let cancelled = false;
    setState({ kind: "loading" });
    Promise.all([
      getMetadata(agentId),
      getUiYaml(agentId).catch(() => null),
    ])
      .then(([metadata, yaml]) => {
        if (cancelled) return;
        if (yaml) {
          setState({ kind: "ready", metadata, ui: yaml, custom: true });
        } else {
          setState({
            kind: "ready",
            metadata,
            ui: defaultChatPage,
            custom: false,
          });
        }
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        const message = e instanceof Error ? e.message : String(e);
        if (/\b404\b/.test(message)) setState({ kind: "missing" });
        else setState({ kind: "error", message });
      });
    return () => {
      cancelled = true;
    };
  }, [agentId]);

  const metadata = state.kind === "ready" ? state.metadata : null;
  const bridge = useMemo(() => {
    if (!metadata) return undefined;
    return new RuntimeBridge(metadata.agent_id, metadata.framework);
  }, [metadata?.agent_id, metadata?.framework]);

  const dispatcher: ActionDispatcher = useMemo(
    () => ({
      async invoke(action: string) {
        if (action === "cancel-run" && bridge) await bridge.cancel();
        return null;
      },
      has(action: string) {
        return action === "cancel-run";
      },
    }),
    [bridge],
  );

  if (state.kind === "loading") return <CenteredNote>Loading agent…</CenteredNote>;

  if (state.kind === "missing") {
    return (
      <CenteredNote tone="muted">
        <p className="text-sm font-medium text-foreground">Agent not found</p>
        <p className="mt-1 text-xs text-muted-foreground">
          No agent with id <code className="mono">{agentId}</code> is loaded.
        </p>
        <Link
          to="/"
          className="mt-4 inline-flex items-center gap-1.5 text-xs font-medium text-primary hover:underline"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to agents
        </Link>
      </CenteredNote>
    );
  }

  if (state.kind === "error") {
    return (
      <CenteredNote tone="error">
        <p className="text-sm font-medium text-destructive">
          Could not load agent
        </p>
        <pre className="mt-2 whitespace-pre-wrap text-[11px] opacity-80">
          {state.message}
        </pre>
      </CenteredNote>
    );
  }

  return (
    <>
      <header className="flex shrink-0 items-center justify-between gap-4 border-b border-border bg-background/40 px-6 py-3 backdrop-blur">
        <div className="flex min-w-0 items-center gap-3">
          <Link
            to="/"
            className="grid h-7 w-7 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-secondary/40 hover:text-foreground"
            title="Back to agents"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h1 className="truncate text-sm font-semibold tracking-tight">
                {state.metadata.name}
              </h1>
              <HealthPill agentId={state.metadata.agent_id} />
            </div>
            <div className="mono mt-0.5 truncate text-muted-foreground">
              {state.metadata.agent_id}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <FrameworkBadge
            framework={state.metadata.framework}
            version={state.metadata.version}
          />
          {!state.custom && (
            <span className="hidden text-[10px] uppercase tracking-wider text-muted-foreground sm:inline">
              default layout
            </span>
          )}
        </div>
      </header>
      <div className="min-h-0 flex-1 overflow-auto px-4 py-4 sm:px-6">
        <AgentUI
          config={state.ui}
          agent={bridge}
          dispatcher={dispatcher}
          diagnostics="console"
        />
      </div>
    </>
  );
}

function CenteredNote({
  children,
  tone = "muted",
}: {
  children: React.ReactNode;
  tone?: "muted" | "error";
}): JSX.Element {
  return (
    <div className="flex min-h-0 flex-1 items-center justify-center p-8">
      <div
        className={`w-full max-w-sm rounded-lg border ${
          tone === "error"
            ? "border-destructive/40 bg-destructive/5"
            : "border-border bg-card/40"
        } px-6 py-8 text-center`}
      >
        {children}
      </div>
    </div>
  );
}
