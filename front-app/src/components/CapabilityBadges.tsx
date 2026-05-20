import type { AgentCapabilities } from "../runtime/types.js";

const ITEMS: { key: keyof AgentCapabilities; label: string }[] = [
  { key: "streaming", label: "stream" },
  { key: "tools", label: "tools" },
  { key: "state", label: "state" },
  { key: "approvals", label: "approvals" },
  { key: "multi_turn", label: "multi-turn" },
];

export function CapabilityBadges({
  capabilities,
}: {
  capabilities: AgentCapabilities;
}): JSX.Element {
  return (
    <div className="flex flex-wrap gap-1">
      {ITEMS.filter((item) => capabilities[item.key]).map((item) => (
        <span
          key={item.key}
          className="inline-flex items-center rounded border border-border/60 bg-muted/30 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground"
        >
          {item.label}
        </span>
      ))}
    </div>
  );
}
