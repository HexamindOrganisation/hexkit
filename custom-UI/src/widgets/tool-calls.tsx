import { useMemo, useState } from "react";
import type { WidgetProps } from "../registry/types.js";
import type {
  ToolCallsWidget,
  ToolCallPayload,
} from "../schema/widgets/tool-calls.js";
import { useAgentInbox } from "../runtime/context.js";
import { cn } from "../lib/utils.js";

/**
 * Live log of tool invocations made by the agent.
 *
 * Wire model: each `tool-call` event routed to this widget carries a
 * `ToolCallPayload`. The widget folds the inbox history into one row per
 * `id` — `start` opens a row, `end` finalizes it. Rows expand on click
 * to reveal arguments and output JSON.
 *
 * No data fetching, no dispatcher calls — this widget is purely a
 * presenter of the bridge's routed events.
 */
export function ToolCallsWidgetComponent({
  props,
}: WidgetProps<ToolCallsWidget>): JSX.Element {
  const { history } = useAgentInbox<ToolCallPayload>();
  const entries = useMemo(() => foldEntries(history), [history]);

  const visible = props.max_items
    ? entries.slice(-props.max_items)
    : entries;

  if (visible.length === 0) {
    return (
      <div className="flex h-full flex-col">
        {props.title && <Header title={props.title} />}
        <div className="flex flex-1 items-center justify-center px-3 text-sm italic text-muted-foreground">
          {props.empty_text ?? "No tool calls yet."}
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      {props.title && <Header title={props.title} />}
      <ul className="flex-1 overflow-y-auto px-2 py-1">
        {visible.map((entry) => (
          <ToolCallRow
            key={entry.id}
            entry={entry}
            defaultExpanded={!!props.default_expanded}
          />
        ))}
      </ul>
    </div>
  );
}

function Header({ title }: { title: string }): JSX.Element {
  return (
    <div className="border-b border-border px-3 py-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
      {title}
    </div>
  );
}

interface FoldedEntry {
  id: string;
  name: string;
  arguments?: Record<string, unknown>;
  output?: unknown;
  error?: string | null;
  /** "running" until an `end` payload arrives for this id. */
  status: "running" | "done" | "error";
}

function foldEntries(history: ToolCallPayload[]): FoldedEntry[] {
  // Preserve first-seen order. We use a Map for O(1) lookup; insertion order
  // is the iteration order so converting back to an array is correct.
  const byId = new Map<string, FoldedEntry>();
  for (const item of history) {
    if (item.phase === "start") {
      // A second `start` for the same id replaces the row — agent loops
      // can re-issue with the same id; we keep the latest start.
      byId.set(item.id, {
        id: item.id,
        name: item.name,
        ...(item.arguments !== undefined && { arguments: item.arguments }),
        status: "running",
      });
    } else {
      const existing = byId.get(item.id);
      const status: FoldedEntry["status"] = item.error ? "error" : "done";
      if (existing) {
        existing.status = status;
        if (item.name) existing.name = item.name;
        if (item.output !== undefined) existing.output = item.output;
        if (item.error !== undefined) existing.error = item.error;
      } else {
        // `end` without a matching `start` — synthesize a one-shot entry.
        byId.set(item.id, {
          id: item.id,
          name: item.name ?? "tool",
          ...(item.output !== undefined && { output: item.output }),
          ...(item.error !== undefined && { error: item.error }),
          status,
        });
      }
    }
  }
  return Array.from(byId.values());
}

function ToolCallRow({
  entry,
  defaultExpanded,
}: {
  entry: FoldedEntry;
  defaultExpanded: boolean;
}): JSX.Element {
  const [expanded, setExpanded] = useState(defaultExpanded);
  return (
    <li className="my-1 rounded-md border border-border bg-card/50">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center justify-between gap-2 px-2 py-1.5 text-left text-sm hover:bg-card"
      >
        <span className="flex min-w-0 items-center gap-2">
          <StatusDot status={entry.status} />
          <span className="truncate font-mono text-xs">{entry.name}</span>
        </span>
        <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
          {expanded ? "hide" : "show"}
        </span>
      </button>
      {expanded && (
        <div className="border-t border-border px-3 py-2 text-xs">
          {entry.arguments !== undefined && (
            <FieldBlock label="Arguments" value={entry.arguments} />
          )}
          {entry.error ? (
            <FieldBlock label="Error" value={entry.error} tone="error" />
          ) : entry.output !== undefined ? (
            <FieldBlock label="Output" value={entry.output} />
          ) : entry.status === "running" ? (
            <p className="italic text-muted-foreground">Running…</p>
          ) : null}
        </div>
      )}
    </li>
  );
}

function StatusDot({
  status,
}: {
  status: FoldedEntry["status"];
}): JSX.Element {
  // HexaUI: amber pulsing (running) → agent accent (done) → rose (error).
  // `bg-primary` is the agent color via the theme bridge (page.main_color).
  const tone =
    status === "running"
      ? "bg-amber-500 animate-pulse"
      : status === "error"
        ? "bg-destructive"
        : "bg-primary";
  return (
    <span
      aria-label={`status: ${status}`}
      className={cn("inline-block h-2 w-2 shrink-0 rounded-full", tone)}
    />
  );
}

function FieldBlock({
  label,
  value,
  tone,
}: {
  label: string;
  value: unknown;
  tone?: "error";
}): JSX.Element {
  return (
    <div className="mb-1.5 last:mb-0">
      <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <pre
        className={cn(
          "mt-0.5 overflow-x-auto whitespace-pre-wrap break-all rounded bg-muted/50 px-2 py-1 font-mono text-[11px]",
          tone === "error" && "text-destructive",
        )}
      >
        {typeof value === "string" ? value : JSON.stringify(value, null, 2)}
      </pre>
    </div>
  );
}
