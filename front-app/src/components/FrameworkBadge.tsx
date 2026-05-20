/**
 * Compact framework + version pill. The accent reflects the framework
 * family — same color for langchain/langgraph/deepagents (shared adapter)
 * vs distinct families for other vendors.
 */
const FAMILY_STYLE: Record<string, string> = {
  langchain:
    "bg-emerald-500/10 text-emerald-300 ring-emerald-500/30",
  langgraph:
    "bg-emerald-500/10 text-emerald-300 ring-emerald-500/30",
  deepagents:
    "bg-emerald-500/10 text-emerald-300 ring-emerald-500/30",
  "openai-agents":
    "bg-stone-500/10 text-stone-200 ring-stone-500/30",
  "google-adk":
    "bg-sky-500/10 text-sky-300 ring-sky-500/30",
};

const DEFAULT_STYLE =
  "bg-muted text-muted-foreground ring-border";

export function FrameworkBadge({
  framework,
  version,
}: {
  framework: string;
  version?: string;
}): JSX.Element {
  const style = FAMILY_STYLE[framework] ?? DEFAULT_STYLE;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider ring-1 ring-inset ${style}`}
    >
      <span>{framework}</span>
      {version && (
        <span className="opacity-70">v{version}</span>
      )}
    </span>
  );
}
