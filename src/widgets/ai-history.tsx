import { useState } from "react";
import type { WidgetProps } from "../registry/types.js";
import type {
  AiHistoryWidget,
  ConversationSummary,
} from "../schema/widgets/ai-history.js";
import {
  useAgentUIContext,
  useWidgetData,
  type ConversationMessage,
} from "../runtime/context.js";
import { cn } from "../lib/utils.js";

export function AiHistoryWidgetComponent({
  props,
  dispatcher,
}: WidgetProps<AiHistoryWidget>): JSX.Element {
  const { data, loading, error } = useWidgetData<ConversationSummary[]>(
    props.data_source,
  );
  const { selectedConversationId, loadConversation } = useAgentUIContext();
  const [busyId, setBusyId] = useState<string | null>(null);

  const conversations = data ?? props.conversations ?? [];

  const handleSelect = async (item: ConversationSummary) => {
    if (busyId === item.id) return;
    setBusyId(item.id);
    try {
      const result = await dispatcher.invoke(props.on_select, { id: item.id });
      const messages = extractMessages(result);
      if (messages) loadConversation(item.id, messages);
    } finally {
      setBusyId(null);
    }
  };

  if (error) {
    return (
      <div className="p-3 text-sm text-destructive">
        Error: {error.message}
      </div>
    );
  }
  if (loading && conversations.length === 0) {
    return (
      <div className="p-3 text-sm italic text-muted-foreground">Loading…</div>
    );
  }
  if (conversations.length === 0) {
    return (
      <div className="p-3 text-sm italic text-muted-foreground">
        {props.empty_text ?? "No past conversations"}
      </div>
    );
  }

  return (
    <ul
      className="m-0 flex h-full list-none flex-col gap-1 overflow-auto p-2"
      role="listbox"
      aria-label="Past conversations"
    >
      {conversations.map((c) => {
        const isSelected = c.id === selectedConversationId;
        const isBusy = busyId === c.id;
        return (
          <li key={c.id}>
            <button
              type="button"
              onClick={() => void handleSelect(c)}
              disabled={isBusy}
              aria-selected={isSelected}
              className={cn(
                "flex w-full flex-col gap-0.5 rounded-md px-3 py-2 text-left transition-colors",
                "hover:bg-accent hover:text-accent-foreground",
                "disabled:cursor-wait disabled:opacity-60",
                isSelected && "bg-accent text-accent-foreground",
              )}
            >
              <span className="truncate text-sm font-medium">{c.title}</span>
              {c.preview && (
                <span className="truncate text-xs text-muted-foreground">
                  {c.preview}
                </span>
              )}
              {c.timestamp !== undefined && (
                <span className="text-[10px] text-muted-foreground">
                  {formatTime(c.timestamp)}
                </span>
              )}
            </button>
          </li>
        );
      })}
    </ul>
  );
}

function extractMessages(result: unknown): ConversationMessage[] | null {
  if (Array.isArray(result)) return result as ConversationMessage[];
  if (result && typeof result === "object" && "messages" in result) {
    const m = (result as { messages?: unknown }).messages;
    if (Array.isArray(m)) return m as ConversationMessage[];
  }
  return null;
}

function formatTime(ts: number): string {
  const d = new Date(ts);
  return d.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
