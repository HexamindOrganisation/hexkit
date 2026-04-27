import { useEffect, useRef } from "react";
import type { WidgetProps } from "../registry/types.js";
import type { AiHistoryWidget } from "../schema/widgets/ai-history.js";
import { useConversation } from "../runtime/context.js";
import { cn } from "../lib/utils.js";

export function AiHistoryWidgetComponent({
  props,
}: WidgetProps<AiHistoryWidget>): JSX.Element {
  const { messages } = useConversation();
  const scrollRef = useRef<HTMLDivElement>(null);
  const showSystem = props.show_system ?? true;
  const visible = showSystem
    ? messages
    : messages.filter((m) => m.role !== "system");

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [visible.length]);

  if (visible.length === 0) {
    return (
      <div className="flex h-full items-center justify-center px-4 py-3 text-sm italic text-muted-foreground">
        {props.empty_text ?? "No conversation yet."}
      </div>
    );
  }

  return (
    <div
      ref={scrollRef}
      className="flex h-full flex-col gap-2 overflow-auto bg-background px-4 py-3"
    >
      {visible.map((m) => (
        <div
          key={m.id}
          className={cn(
            "flex flex-col gap-0.5",
            m.role === "user" && "items-end",
            m.role === "assistant" && "items-start",
            m.role === "system" && "items-center",
          )}
        >
          <span
            className={cn(
              "max-w-[80%] whitespace-pre-wrap break-words rounded-md px-3 py-2 text-sm",
              m.role === "user" && "bg-primary text-primary-foreground",
              m.role === "assistant" && "bg-accent text-accent-foreground",
              m.role === "system" &&
                "bg-muted text-xs italic text-muted-foreground",
            )}
          >
            {m.content}
          </span>
          <span className="text-[10px] text-muted-foreground">
            {formatTime(m.timestamp)} · {m.role}
          </span>
        </div>
      ))}
    </div>
  );
}

function formatTime(ts: number): string {
  const d = new Date(ts);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}
