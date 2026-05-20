import { Link } from "react-router-dom";
import { ArrowUpRight } from "lucide-react";
import type { AgentMetadata } from "../runtime/types.js";
import { CapabilityBadges } from "./CapabilityBadges.js";
import { FrameworkBadge } from "./FrameworkBadge.js";
import { HealthPill } from "./HealthPill.js";

export function AgentCard({ agent }: { agent: AgentMetadata }): JSX.Element {
  const model =
    typeof agent.extra?.model === "string"
      ? (agent.extra.model as string)
      : null;

  return (
    <Link
      to={`/agents/${encodeURIComponent(agent.agent_id)}`}
      className="group relative flex h-full flex-col gap-3 overflow-hidden rounded-lg border border-border/80 bg-card/50 p-5 transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:bg-card hover:shadow-lg hover:shadow-primary/5"
    >
      <span className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-primary/30 to-transparent opacity-0 transition-opacity group-hover:opacity-100" />

      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-base font-semibold leading-tight tracking-tight">
            {agent.name}
          </div>
          <div className="mono mt-0.5 truncate text-muted-foreground">
            {agent.agent_id}
          </div>
        </div>
        <HealthPill agentId={agent.agent_id} />
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        <FrameworkBadge framework={agent.framework} version={agent.version} />
        <CapabilityBadges capabilities={agent.capabilities} />
      </div>

      {agent.description && (
        <p className="line-clamp-2 text-xs leading-relaxed text-muted-foreground">
          {agent.description.replace(/\s+/g, " ").trim()}
        </p>
      )}

      <div className="mt-auto flex items-center justify-between border-t border-border/60 pt-3">
        <span className="mono truncate text-muted-foreground">
          {model ?? "—"}
        </span>
        <span className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground transition-colors group-hover:text-primary">
          Open chat
          <ArrowUpRight className="h-3.5 w-3.5" />
        </span>
      </div>
    </Link>
  );
}
